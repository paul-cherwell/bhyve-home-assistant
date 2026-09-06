"""Support for Orbit BHyve sensors."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util import dt

from . import BHyveCoordinatorEntity
from .const import (
    DEVICE_FLOOD,
    DEVICE_SPRINKLER,
    DOMAIN,
)
from .util import orbit_time_to_local_time

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import BHyveDataUpdateCoordinator
    from .pybhyve.typings import BHyveDevice

_LOGGER = logging.getLogger(__name__)

ATTR_BUDGET = "budget"
ATTR_CONSUMPTION_GALLONS = "consumption_gallons"
ATTR_CONSUMPTION_LITRES = "consumption_litres"
ATTR_IRRIGATION = "irrigation"
ATTR_PROGRAM = "program"
ATTR_PROGRAM_NAME = "program_name"
ATTR_RUN_TIME = "run_time"
ATTR_NEXT_START_PROGRAMS = "programs"
ATTR_START_TIME = "start_time"
ATTR_STATUS = "status"

# landscape attrs (editable)
ATTR_APPLICATION_RATE = "application_rate"
ATTR_EFFICIENCY = "efficiency"
ATTR_PLANT_FACTOR = "plant_factor"
ATTR_MICROCLIMATE_FACTOR = "micro_climate"
ATTR_MGMT_ALLOWED_DEPLETION = "max_allowable_depletion"
ATTR_FIELD_CAPACITY = "field_capacity"
ATTR_PERMANENT_WILTING_POINT = "permanent_wilting_point"
ATTR_ROOT_ZONE = "root_depth"
ATTR_ALLOWABLE_SURFACE_ACCUMULATION = "allowable_soil_acc"
ATTR_BASIC_INFILTRATION_RATE = "infiltration_rate"
ATTR_EFFECTIVE_RAINFALL = "rainfall_efficiency"
ATTR_DROUGHT_FACTOR = "drought_factor"

# landscape attrs (computed)
ATTR_AVAILABLE_WATER = "available_water"
ATTR_FIELD_CAPACITY_DEPTH = "field_capacity_depth"
ATTR_PERMANENT_WILTING_POINT_DEPTH = "pwp_depth"
ATTR_PLANT_AVAILABLE_WATER = "plant_available_water"
ATTR_READILY_AVAILABLE_WATER = "readily_available_water"
ATTR_REFILL_POINT = "replenishment_point"
ATTR_MAXIMUM_RUNTIME_BEFORE_RUNOFF = "max_runtime"
ATTR_LANDSCAPE_COEFFICIENT = "landscape_coefficient"

# program.watering_plan[0].zone_forecasts attrs
ATTR_LANDSCAPE_EVAPOTRANSPIRATION = "etc"
ATTR_REFERENCE_EVAPOTRANSPIRATION = "eto"

# calculated attrs
ATTR_STANDARD_RUNTIME = "standard_runtime"
ATTR_CURRENT_MOISTURE_BALANCE = "current_moisture_balance"


def _parse_battery_level(battery_data: dict) -> int:
    """
    Parse battery level data and return as percentage.

    If the 'percent' attribute is present in the battery data, it is used.
    Otherwise, if the 'mv' attribute is present, the battery level is
    calculated as a percentage based on millivolts, assuming 2x1.5V AA
    batteries. Note that AA batteries can range from 1.2V to 1.7V depending
    on their chemistry, so the calculation may not be accurate for all types.

    Args:
    ----
    battery_data (dict): A dictionary containing the battery data.

    Returns:
    -------
    int: The battery level as a percentage.

    """
    if not isinstance(battery_data, dict):
        _LOGGER.warning("Unexpected battery data, returning 0: %s", battery_data)
        return 0

    battery_level = battery_data.get("percent", 0)
    if "mv" in battery_data and "percent" not in battery_data:
        battery_level = min(battery_data.get("mv", 0) / 3000 * 100, 100)
    return int(battery_level)


@dataclass(frozen=True, kw_only=True)
class BHyveSensorEntityDescription(SensorEntityDescription):
    """Describes BHyve sensor entity."""

    unique_id_suffix: str
    name: str = ""
    # Callable that takes device_data and returns value
    value_fn: Any = None
    # Callable that takes device_data and returns attributes
    attributes_fn: Any = None
    # Callable that takes device_data and native_value, returns icon
    icon_fn: Any = None
    # Callable that takes device_data and native_value, returns bool
    available_fn: Any = None


SENSOR_TYPES_SPRINKLER: tuple[BHyveSensorEntityDescription, ...] = (
    BHyveSensorEntityDescription(
        key="state",
        translation_key="state",
        name="State",
        icon="mdi:information",
        unique_id_suffix="state",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("status", {}).get("run_mode", "unavailable"),
    ),
    BHyveSensorEntityDescription(
        key="next_watering",
        translation_key="next_watering",
        name="Next watering",
        unique_id_suffix="next_watering",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:sprinkler-variant",
        value_fn=lambda data: orbit_time_to_local_time(
            data.get("status", {}).get("next_start_time")
        ),
        attributes_fn=lambda data: (
            {ATTR_NEXT_START_PROGRAMS: programs}
            if (programs := data.get("status", {}).get("next_start_programs"))
            else {}
        ),
    ),
)

SENSOR_TYPES_FLOOD: tuple[BHyveSensorEntityDescription, ...] = (
    BHyveSensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        name="Temperature sensor",
        icon="mdi:thermometer",
        unique_id_suffix="temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        value_fn=lambda data: (
            float(temp)
            if (temp := data.get("status", {}).get("temp_f")) is not None
            else None
        ),
        attributes_fn=lambda data: {
            "location": data.get("location_name"),
        },
        available_fn=lambda _data, value: value is not None,
    ),
    BHyveSensorEntityDescription(
        key="rssi",
        translation_key="signal_strength",
        name="Signal strength",
        unique_id_suffix="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("status", {}).get("rssi"),
    ),
)

SENSOR_TYPES_BATTERY: tuple[BHyveSensorEntityDescription, ...] = (
    BHyveSensorEntityDescription(
        key="battery",
        translation_key="battery",
        name="Battery level",
        icon="mdi:battery",
        unique_id_suffix="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            _parse_battery_level(battery) if (battery := data.get("battery")) else None
        ),
        attributes_fn=lambda data: (
            {ATTR_BATTERY_LEVEL: level}
            if (battery := data.get("battery"))
            and (level := _parse_battery_level(battery))
            else {}
        ),
        icon_fn=lambda _data, value: (
            icon_for_battery_level(battery_level=int(value), charging=False)
            if value is not None
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the BHyve sensor platform from a config entry."""
    coordinator: BHyveDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    devices: list[BHyveDevice] = hass.data[DOMAIN][entry.entry_id]["devices"]

    sensors = []

    for device in devices:
        if device.get("type") == DEVICE_SPRINKLER:
            # Add state sensors
            for base_description in SENSOR_TYPES_SPRINKLER:
                description = BHyveSensorEntityDescription(
                    key=base_description.key,
                    translation_key=base_description.translation_key,
                    name=base_description.name,
                    icon=base_description.icon,
                    unique_id_suffix=base_description.unique_id_suffix,
                    device_class=base_description.device_class,
                    entity_category=base_description.entity_category,
                    value_fn=base_description.value_fn,
                    attributes_fn=base_description.attributes_fn,
                    icon_fn=base_description.icon_fn,
                    available_fn=base_description.available_fn,
                )
                sensors.append(BHyveSensor(coordinator, device, description))

            # Add zone history and smart watering soil sensors
            all_zones = device.get("zones", [])
            for zone in all_zones:
                # if the zone doesn't have a name, set it to the device's name if
                # there is only one (eg a hose timer)
                zone_name: str = zone.get("name") or (
                    device.get("name", "Unnamed Zone")
                    if len(all_zones) == 1
                    else "Unnamed Zone"
                )
                sensors.append(
                    BHyveZoneHistorySensor(
                        coordinator,
                        device,
                        zone,
                        zone_name,
                        SensorEntityDescription(
                            key="zone_history",
                            translation_key="zone_history",
                            icon="mdi:history",
                            device_class=SensorDeviceClass.TIMESTAMP,
                            entity_category=EntityCategory.DIAGNOSTIC,
                        ),
                    )
                )
                if zone["smart_watering_enabled"]:
                    sensors.append(
                        BHyveSmartWateringZoneSensor(
                            coordinator,
                            device,
                            zone,
                            zone_name,
                            SensorEntityDescription(
                                key="smart_watering_zone",
                                translation_key="smart_watering_zone",
                                icon="mdi:water-percent",
                                device_class=SensorDeviceClass.MOISTURE,
                                entity_category=EntityCategory.DIAGNOSTIC,
                                native_unit_of_measurement=PERCENTAGE,
                            ),
                        )
                    )

            # Add battery sensor if device has battery
            if device.get("battery", None) is not None:
                for base_description in SENSOR_TYPES_BATTERY:
                    description = BHyveSensorEntityDescription(
                        key=base_description.key,
                        translation_key=base_description.translation_key,
                        name=base_description.name,
                        icon=base_description.icon,
                        unique_id_suffix=base_description.unique_id_suffix,
                        device_class=base_description.device_class,
                        state_class=base_description.state_class,
                        native_unit_of_measurement=base_description.native_unit_of_measurement,
                        entity_category=base_description.entity_category,
                        value_fn=base_description.value_fn,
                        attributes_fn=base_description.attributes_fn,
                        icon_fn=base_description.icon_fn,
                        available_fn=base_description.available_fn,
                    )
                    sensors.append(BHyveSensor(coordinator, device, description))

        if device.get("type") == DEVICE_FLOOD:
            # Add temperature and RSSI sensors
            for base_description in SENSOR_TYPES_FLOOD:
                description = BHyveSensorEntityDescription(
                    key=base_description.key,
                    translation_key=base_description.translation_key,
                    name=base_description.name,
                    icon=base_description.icon,
                    unique_id_suffix=base_description.unique_id_suffix,
                    device_class=base_description.device_class,
                    state_class=base_description.state_class,
                    native_unit_of_measurement=base_description.native_unit_of_measurement,
                    entity_category=base_description.entity_category,
                    value_fn=base_description.value_fn,
                    attributes_fn=base_description.attributes_fn,
                    icon_fn=base_description.icon_fn,
                    available_fn=base_description.available_fn,
                )
                sensors.append(BHyveSensor(coordinator, device, description))

            # Add battery sensor
            for base_description in SENSOR_TYPES_BATTERY:
                description = BHyveSensorEntityDescription(
                    key=base_description.key,
                    translation_key=base_description.translation_key,
                    name=base_description.name,
                    icon=base_description.icon,
                    unique_id_suffix=base_description.unique_id_suffix,
                    device_class=base_description.device_class,
                    state_class=base_description.state_class,
                    native_unit_of_measurement=base_description.native_unit_of_measurement,
                    entity_category=base_description.entity_category,
                    value_fn=base_description.value_fn,
                    attributes_fn=base_description.attributes_fn,
                    icon_fn=base_description.icon_fn,
                    available_fn=base_description.available_fn,
                )
                sensors.append(BHyveSensor(coordinator, device, description))

    async_add_entities(sensors)


class BHyveSensor(BHyveCoordinatorEntity, SensorEntity):
    """Define a BHyve sensor."""

    entity_description: BHyveSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BHyveDataUpdateCoordinator,
        device: BHyveDevice,
        description: BHyveSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = description.name
        super().__init__(coordinator, device)
        self._attr_unique_id = (
            f"{self._mac_address}:{self._device_id}:{description.unique_id_suffix}"
        )

    @property
    def native_value(self) -> datetime | int | float | str | None:
        """Return the state of the entity."""
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(self.device_data)
        return None

    @property
    def icon(self) -> str | None:
        """Icon to use in the frontend, if any."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(self.device_data, self.native_value)
        return super().icon

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.device_data)
        return {}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if self.entity_description.available_fn:
            return super().available and self.entity_description.available_fn(
                self.device_data, self.native_value
            )
        return super().available


class BHyveZoneHistorySensor(BHyveCoordinatorEntity, SensorEntity):
    """Define a BHyve zone history sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BHyveDataUpdateCoordinator,
        device: BHyveDevice,
        zone: dict,
        zone_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        if zone_name == device.get("name"):
            self._attr_name = "Zone history"
        else:
            self._attr_name = f"{zone_name} zone history"
        self._attr_translation_placeholders = {"zone_name": zone_name}
        super().__init__(coordinator, device)

        self._zone = zone
        self._zone_id = zone.get("station")
        self._attr_unique_id = (
            f"{self._mac_address}:{self._device_id}:{self._zone_id}:history"
        )

    @property
    def native_value(self) -> datetime | None:
        """Return the state of the entity."""
        latest = self._get_latest_irrigation()
        if not latest:
            return None
        start_time = latest.get(ATTR_START_TIME)
        if start_time:
            return orbit_time_to_local_time(start_time)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        latest = self._get_latest_irrigation()
        if not latest:
            return {}

        gallons = latest.get("water_volume_gal")
        litres = round(gallons * 3.785, 2) if gallons else None

        return {
            ATTR_BUDGET: latest.get(ATTR_BUDGET),
            ATTR_PROGRAM: latest.get(ATTR_PROGRAM),
            ATTR_PROGRAM_NAME: latest.get(ATTR_PROGRAM_NAME),
            ATTR_RUN_TIME: latest.get(ATTR_RUN_TIME),
            ATTR_STATUS: latest.get(ATTR_STATUS),
            ATTR_CONSUMPTION_GALLONS: gallons,
            ATTR_CONSUMPTION_LITRES: litres,
            ATTR_START_TIME: latest.get(ATTR_START_TIME),
        }

    def _get_latest_irrigation(self) -> dict | None:
        """
        Return the irrigation entry with the greatest start_time for this zone.

        All statuses are considered — skipped runs can still report flow
        consumption. Ordering is derived from start_time rather than array
        position so we don't depend on how the upstream API sorts entries.
        """
        latest: dict | None = None
        latest_start: str | None = None
        for history_item in self._get_device_history():
            for irrigation in history_item.get(ATTR_IRRIGATION, []):
                if irrigation.get("station") != self._zone_id:
                    continue
                start_time = irrigation.get(ATTR_START_TIME)
                if not start_time:
                    continue
                if latest_start is None or start_time > latest_start:
                    latest_start = start_time
                    latest = irrigation
        return latest

    def _get_device_history(self) -> list:
        """Get device history from coordinator."""
        return (
            self.coordinator.data.get("devices", {})
            .get(self._device_id, {})
            .get("history", [])
        )


class BHyveSmartWateringZoneSensor(BHyveCoordinatorEntity, SensorEntity):
    # see https://husqvarna-water.com/smart-watering-101/ for formulas
    """Define a BHyve smart watering zone sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BHyveDataUpdateCoordinator,
        device: BHyveDevice,
        zone: dict,
        zone_name: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        if zone_name == device.get("name"):
            self._attr_name = "Smart watering"
        else:
            self._attr_name = f"{zone_name} smart watering"
        self._attr_translation_placeholders = {"zone_name": zone_name}
        super().__init__(coordinator, device)

        self._zone = zone
        self._zone_id = zone.get("station")
        self._attr_unique_id = (
            f"{self._mac_address}:{self._device_id}:{self._zone_id}:smart_watering_zone"
        )

    @property
    def native_value(self) -> int | None:
        """Return the state of the entity."""
        landscape = self._get_landscape()
        if not landscape:
            return None
        # B-hyve computed value for 0% moisture
        landscape_moisture_level_0 = landscape["replenishment_point"]

        # B-hyve computed value for 100% moisture
        landscape_moisture_level_100 = landscape["field_capacity_depth"]

        # B-hyve reported current moisture
        landscape_moisture_level = self._get_current_moisture_balance()
        if (
            landscape_moisture_level_0 is None
            or landscape_moisture_level_100 is None
            or landscape_moisture_level is None
        ):
            return None

        landscape_moisture_percentage = (
            (landscape_moisture_level - landscape_moisture_level_0)
            / (landscape_moisture_level_100 - landscape_moisture_level_0)
        ) * 100

        return max(0, min(100, round(landscape_moisture_percentage)))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        landscape = self._get_landscape()
        if not landscape:
            return {}

        zone_forcast = self._get_zone_forecast()
        if not zone_forcast:
            return {}

        return {
            # editable
            ATTR_APPLICATION_RATE: landscape.get(ATTR_APPLICATION_RATE),
            ATTR_EFFICIENCY: landscape.get(ATTR_EFFICIENCY),
            ATTR_PLANT_FACTOR: landscape.get(ATTR_PLANT_FACTOR),
            ATTR_MICROCLIMATE_FACTOR: landscape.get(ATTR_MICROCLIMATE_FACTOR),
            ATTR_MGMT_ALLOWED_DEPLETION: landscape.get(ATTR_MGMT_ALLOWED_DEPLETION),
            ATTR_FIELD_CAPACITY: landscape.get(ATTR_FIELD_CAPACITY),
            ATTR_PERMANENT_WILTING_POINT: landscape.get(ATTR_PERMANENT_WILTING_POINT),
            ATTR_ROOT_ZONE: landscape.get(ATTR_ROOT_ZONE),
            ATTR_ALLOWABLE_SURFACE_ACCUMULATION: landscape.get(
                ATTR_ALLOWABLE_SURFACE_ACCUMULATION
            ),
            ATTR_BASIC_INFILTRATION_RATE: landscape.get(ATTR_BASIC_INFILTRATION_RATE),
            ATTR_EFFECTIVE_RAINFALL: landscape.get(ATTR_EFFECTIVE_RAINFALL),
            ATTR_DROUGHT_FACTOR: landscape.get(ATTR_DROUGHT_FACTOR),
            # computed
            ATTR_AVAILABLE_WATER: landscape.get(ATTR_AVAILABLE_WATER),
            ATTR_FIELD_CAPACITY_DEPTH: landscape.get(ATTR_FIELD_CAPACITY_DEPTH),
            ATTR_PERMANENT_WILTING_POINT_DEPTH: landscape.get(
                ATTR_PERMANENT_WILTING_POINT_DEPTH
            ),
            ATTR_PLANT_AVAILABLE_WATER: landscape.get(ATTR_PLANT_AVAILABLE_WATER),
            ATTR_READILY_AVAILABLE_WATER: landscape.get(ATTR_READILY_AVAILABLE_WATER),
            ATTR_REFILL_POINT: landscape.get(ATTR_REFILL_POINT),
            ATTR_STANDARD_RUNTIME: self._get_standard_runtime_minutes(),
            ATTR_MAXIMUM_RUNTIME_BEFORE_RUNOFF: landscape.get(
                ATTR_MAXIMUM_RUNTIME_BEFORE_RUNOFF
            ),
            ATTR_REFERENCE_EVAPOTRANSPIRATION: zone_forcast.get(
                ATTR_REFERENCE_EVAPOTRANSPIRATION
            ),
            ATTR_LANDSCAPE_COEFFICIENT: landscape.get(ATTR_LANDSCAPE_COEFFICIENT),
            ATTR_LANDSCAPE_EVAPOTRANSPIRATION: zone_forcast.get(
                ATTR_LANDSCAPE_EVAPOTRANSPIRATION
            ),
            ATTR_CURRENT_MOISTURE_BALANCE: self._get_current_moisture_balance(),
        }

    def _get_standard_runtime_minutes(self) -> int | None:
        """Calculate standard runtime based on values from the landscape."""
        landscape = self._get_landscape()
        if not landscape:
            return None

        readily_available_water = landscape.get(ATTR_READILY_AVAILABLE_WATER)
        application_rate = landscape.get(ATTR_APPLICATION_RATE)
        efficiency = landscape.get(ATTR_EFFICIENCY)

        if (
            readily_available_water is None
            or application_rate is None
            or efficiency is None
        ):
            return None

        standard_runtime_hours = (
            readily_available_water / application_rate
        ) / efficiency

        return round(standard_runtime_hours * 60)

    def _get_current_moisture_balance(self) -> float | None:
        """Calculate current moisture balance based on values from the zone forecast."""
        zone_forcast = self._get_zone_forecast()
        if not zone_forcast:
            return None

        landscape = self._get_landscape()
        if not landscape:
            return None

        initial_moisture_balance = zone_forcast.get("initial_water_level")

        reference_evapotranspiration = zone_forcast.get(
            ATTR_REFERENCE_EVAPOTRANSPIRATION
        )
        landscape_coefficient = landscape.get(ATTR_LANDSCAPE_COEFFICIENT)
        if reference_evapotranspiration is None or landscape_coefficient is None:
            return None

        landscape_evapotranspiration = (
            reference_evapotranspiration * landscape_coefficient
        )

        effective_rainfall = zone_forcast.get("effective_rainfall")

        effective_irrigation = zone_forcast.get("effective_irrigation")

        if (
            initial_moisture_balance is None
            or landscape_evapotranspiration is None
            or effective_rainfall is None
            or effective_irrigation is None
        ):
            return None

        local_tz = dt.get_default_time_zone()

        now = datetime.now(local_tz)

        nine_am = now.replace(hour=9, minute=0, second=0, microsecond=0)

        nine_pm = now.replace(hour=21, minute=0, second=0, microsecond=0)

        current_moisture_balance: float | None
        if now < nine_am:
            current_moisture_balance = initial_moisture_balance
        elif now < nine_pm:
            daylight_hours_elapsed = (now - nine_am).total_seconds() / 3600
            total_daylight_hours = 12
            evapotranspiration_loss = landscape_evapotranspiration * (
                daylight_hours_elapsed / total_daylight_hours
            )
            current_moisture_balance = (
                initial_moisture_balance
                - evapotranspiration_loss
                + effective_rainfall
                + effective_irrigation
            )
        else:
            current_moisture_balance = zone_forcast.get("final_water_level")

        return current_moisture_balance

    def _get_landscape(self) -> dict | None:
        """Return the landscape entry for this zone."""
        landscapes = self._get_device_landscapes()
        return landscapes.get(str(self._zone_id))

    def _get_device_landscapes(self) -> dict:
        """Get landscapes from coordinator."""
        return (
            self.coordinator.data.get("devices", {})
            .get(self._device_id, {})
            .get("landscapes", [])
        )

    def _get_zone_forecast(self) -> dict | None:
        """Return the current day's watering forecast for this zone."""
        smart_program = self._get_smart_watering_program()
        if not smart_program:
            return {}

        watering_plan = smart_program.get("watering_plan")
        if not watering_plan:
            return {}

        current_day_forecasts = watering_plan[0].get("zone_forecasts")
        if not current_day_forecasts:
            return {}

        zone_forecast: dict | None = None
        for forecast in current_day_forecasts:
            if forecast.get("station") == self._zone_id:
                zone_forecast = forecast
                break

        return zone_forecast

    def _get_smart_watering_program(self) -> dict | None:
        """Get smart watering program for this device."""
        smart_program: dict | None = None

        for program in self._get_programs().values():
            if not program.get("is_smart_program"):
                continue

            device_id = program.get("device_id")
            if not device_id:
                continue

            if device_id == self._device_id:
                smart_program = program
                break

        return smart_program

    def _get_programs(self) -> dict:
        """Get programs from coordinator."""
        return self.coordinator.data.get("programs", {})
