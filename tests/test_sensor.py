"""Test BHyve sensor entities."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature

from custom_components.bhyve.coordinator import BHyveDataUpdateCoordinator
from custom_components.bhyve.pybhyve.typings import BHyveDevice
from custom_components.bhyve.sensor import (
    SENSOR_TYPES_BATTERY,
    SENSOR_TYPES_FLOOD,
    SENSOR_TYPES_SPRINKLER,
    BHyveSensor,
    BHyveSensorEntityDescription,
    BHyveSmartWateringZoneSensor,
    BHyveZoneHistorySensor,
)

# Test constants
TEST_BATTERY_LEVEL = 85
TEST_BATTERY_LEVEL_UPDATED = 50
TEST_TEMPERATURE_FAHRENHEIT = 72.5


def create_mock_coordinator(devices: dict, programs: dict | None = None) -> MagicMock:
    """Create a mock coordinator with the given devices."""
    if programs is None:
        programs = {}

    coordinator = MagicMock(spec=BHyveDataUpdateCoordinator)
    coordinator.data = {
        "devices": devices,
        "programs": programs,
    }
    coordinator.last_update_success = True
    coordinator.async_set_updated_data = MagicMock()
    coordinator.client = MagicMock()
    coordinator.client.send_message = AsyncMock()
    return coordinator


def create_sensor_description(
    _device: BHyveDevice, base_description: BHyveSensorEntityDescription
) -> BHyveSensorEntityDescription:
    """Create a sensor description with device name for testing."""
    return BHyveSensorEntityDescription(
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


@pytest.fixture
def mock_sprinkler_device_with_battery() -> BHyveDevice:
    """Mock BHyve sprinkler device with battery data."""
    return BHyveDevice(
        {
            "id": "test-device-123",
            "name": "Test Sprinkler",
            "type": "sprinkler_timer",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "hardware_version": "v2.0",
            "firmware_version": "1.2.3",
            "is_connected": True,
            "battery": {
                "percent": TEST_BATTERY_LEVEL,
                "charging": False,
            },
            "status": {
                "run_mode": "auto",
                "watering_status": None,
            },
            "zones": [{"station": "1", "name": "Front Lawn"}],
        }
    )


@pytest.fixture
def mock_flood_device() -> BHyveDevice:
    """Mock BHyve flood sensor device."""
    return BHyveDevice(
        {
            "id": "test-flood-456",
            "name": "Test Flood Sensor",
            "type": "flood_sensor",
            "mac_address": "bb:cc:dd:ee:ff:aa",
            "hardware_version": "v1.0",
            "firmware_version": "2.1.0",
            "is_connected": True,
            "battery": {
                "percent": 90,
                "charging": False,
            },
            "status": {
                "temp_f": TEST_TEMPERATURE_FAHRENHEIT,
                "rssi": -45,
                "temp_alarm_status": "ok",
            },
            "location_name": "Basement",
        }
    )


@pytest.fixture
def mock_zone_history_data() -> list:
    """Mock zone history data."""
    return [
        {
            "irrigation": [
                {
                    "station": "1",
                    "budget": 100,
                    "program": "a",
                    "program_name": "Morning Schedule",
                    "run_time": 15,
                    "status": "complete",
                    "water_volume_gal": 25.5,
                    "start_time": "2020-01-09T20:15:00.000Z",
                }
            ]
        }
    ]


@pytest.fixture
def mock_smart_watering_landscapes_data() -> dict:
    """Mock smart watering landscapes data."""
    return {
        "1": {
            "station": 1,
            "root_depth": 12,
            "max_allowable_depletion": 0.35,
            "pwp_depth": 2.16,
            "permanent_wilting_point": 0.18,
            "allowable_soil_acc": 0.26,
            "field_capacity_depth": 3.84,
            "replenishment_point": 3.252,
            "plant_available_water": 1.6799999999999997,
            "max_runtime": 0,
            "drought_factor": 1,
            "micro_climate": 0.9,
            "plant_factor": 0.7,
            "available_water": 0.14,
            "current_water_level": 3.252,
            "application_rate": 31.857641025641016,
            "field_capacity": 0.32,
            "updated_at": "2026-08-20T18:00:00.000Z",
            "distribution_uniformity": 0.8766692851531815,
            "rainfall_efficiency": 0.63,
            "min_water_level": 3.252,
            "id": "a",
            "landscape_coeffcient": 0.63,
            "infiltration_rate": 0.2,
            "monthly_eto": [
                1.48273003101,
                1.90748000145,
                2.62103009224,
                3.96890997887,
                4.96686983109,
                6.26438999176,
                6.55533981323,
                5.66915988922,
                4.48599004745,
                3.33847999573,
                1.92864000797,
                1.44123995304,
            ],
            "efficiency": 0.1356191102586882,
            "device_id": "test-device-123",
            "readily_available_water": 0.5879999999999999,
            "created_at": "2026-08-19T18:00:00.000Z",
            "scheduling_multiplier": 1.0799117746861213,
        },
        "2": {
            "station": 2,
            "root_depth": 6,
            "max_allowable_depletion": 0.35,
            "pwp_depth": 1.62,
            "permanent_wilting_point": 0.27,
            "allowable_soil_acc": 0.16,
            "field_capacity_depth": 2.58,
            "replenishment_point": 2.244,
            "plant_available_water": 0.96,
            "max_runtime": 22,
            "drought_factor": 1,
            "micro_climate": 1,
            "plant_factor": 0.8,
            "available_water": 0.15999999999999998,
            "application_rate": 0.5727296703296705,
            "field_capacity": 0.43,
            "updated_at": "2026-08-20T18:00:00.000Z",
            "distribution_uniformity": 0.7668539325842697,
            "rainfall_efficiency": 0.4,
            "min_water_level": 2.244,
            "id": "b",
            "landscape_coefficient": 0.8,
            "infiltration_rate": 0.15,
            "monthly_eto": [
                1.48273003101,
                1.90748000145,
                2.62103009224,
                3.96890997887,
                4.96686983109,
                6.26438999176,
                6.55533981323,
                5.66915988922,
                4.48599004745,
                3.33847999573,
                1.92864000797,
                1.44123995304,
            ],
            "efficiency": 0.5845321186787661,
            "device_id": "test-device-123",
            "readily_available_water": 0.33599999999999997,
            "created_at": "2026-08-19T18:00:00.000Z",
            "scheduling_multiplier": 1.1626387981711301,
        },
    }


@pytest.fixture
def mock_smart_watering_programs_data() -> dict:
    """Mock smart watering programs data."""
    return {
        "a": {
            "name": "Manual",
            "program_start_date": "2026-08-18T06:00:00.000Z",
            "frequency": {"type": "days", "days": [1, 3, 6]},
            "program_end_date": None,
            "updated_at": "2026-08-19T010:00:00.000Z",
            "updated_via": "wifi",
            "start_times": ["05:30", "07:00"],
            "id": "a",
            "budget": 100,
            "is_smart_program": False,
            "device_id": "test-device-123",
            "program": "a",
            "run_times": [{"run_time": 30, "station": 1}],
            "enabled": True,
            "created_at": "2026-08-17T012:00:00.000Z",
        },
        "b": {
            "post_delay": 0.0,
            "lock_at": "2026-08-31T08:00:00.000Z",
            "name": "Smart Watering",
            "frequency": {"type": "days", "days": [1, 3, 6]},
            "process_at": "2026-08-31T14:18:00.000Z",
            "watering_plan": [
                {
                    "date": "2026-08-29T08:00:00.000Z",
                    "start_times": [],
                    "run_times": [],
                    "zone_forecasts": [
                        {
                            "station": 2,
                            "initial_water_level": 3.5034046142773994,
                            "date": "2026-08-29T08:00:00.000Z",
                            "eto": 0.29325470937656308,
                            "mbo_raw": 0.35940461427739914,
                            "net_irrigation": 0.0,
                            "total_soak_runoff": 0,
                            "total_direct_runoff": 0,
                            "gross_irrigation": 0.0,
                            "water_rule": "system_restricted",
                            "rainfall": 0,
                            "etc": 0.2546037675012505,
                            "final_water_level": 2.5034046142773994,
                            "delta": -1,
                            "total_scheduling_losses": 0,
                            "daily_surplus": 0,
                            "device_id": "test-device-123",
                            "soak_runoff": [],
                            "mbf_raw": 0.20480084677614876,
                            "effective_rainfall": 0.0,
                            "effective_irrigation": 0.0,
                            "direct_runoff": [],
                        }
                    ],
                },
                {
                    "date": "2026-08-30T08:00:00.000Z",
                    "start_times": [],
                    "run_times": [],
                    "zone_forecasts": [
                        {
                            "station": 2,
                            "initial_water_level": 2.5034046142773994,
                            "date": "2026-08-30T08:00:00.000Z",
                            "eto": 0.19325470937656308,
                            "mbo_raw": 0.25940461427739914,
                            "net_irrigation": 0.0,
                            "total_soak_runoff": 0,
                            "total_direct_runoff": 0,
                            "gross_irrigation": 0.0,
                            "water_rule": "system_restricted",
                            "rainfall": 0,
                            "etc": 0.1546037675012505,
                            "final_water_level": 2.348800846776149,
                            "delta": -0.15460376750125038,
                            "total_scheduling_losses": 0,
                            "daily_surplus": 0,
                            "device_id": "test-device-123",
                            "soak_runoff": [],
                            "mbf_raw": 0.10480084677614876,
                            "effective_rainfall": 0.2,
                            "effective_irrigation": 0.3,
                            "direct_runoff": [],
                        }
                    ],
                },
                {
                    "date": "2026-08-31T08:00:00.000Z",
                    "start_times": ["02:00", "03:15", "04:30"],
                    "run_times": [
                        {"station": 2, "run_time": 75, "device_id": "test-device-123"}
                    ],
                    "zone_forecasts": [
                        {
                            "station": 2,
                            "initial_water_level": 2.348800846776149,
                            "date": "2026-08-31T08:00:00.000Z",
                            "eto": 0.1556276452562946,
                            "mbo_raw": 0.10480084677614876,
                            "net_irrigation": 0.3347788876279935,
                            "total_soak_runoff": 0,
                            "total_direct_runoff": 0,
                            "gross_irrigation": 0.5727296703296705,
                            "water_rule": "as-needed",
                            "rainfall": 0,
                            "etc": 0.12450211620503569,
                            "final_water_level": 2.559077618199107,
                            "delta": 0.05567300392170749,
                            "total_scheduling_losses": 0,
                            "daily_surplus": 0,
                            "device_id": "test-device-123",
                            "soak_runoff": [0, 0],
                            "mbf_raw": 0.3150776181991066,
                            "effective_rainfall": 0.0,
                            "effective_irrigation": 0.0,
                            "direct_runoff": [0, 0, 0],
                        }
                    ],
                },
            ],
            "long_term_program": {
                "frequency": {
                    "type": "interval",
                    "intervals": [9, 7, 5, 4, 3, 3, 2, 3, 3, 4, 7, 10],
                },
                "run_times": [{"run_time": 75, "station": 2}],
                "group_run_times": [
                    {
                        "device_id": "test-device-123",
                        "run_times": [{"run_time": 75, "station": 2}],
                    }
                ],
                "start_times": ["02:00", "03:45", "05:30"],
                "budgets": [0, 0, 0, 90, 80, 100, 80, 90, 80, 80, 0, 0],
                "pre_delay": 0,
                "post_delay": 0.0,
            },
            "group_id": "1",
            "updated_at": "2026-08-30T21:00:00.000Z",
            "pre_delay": 0,
            "updated_via": "wifi",
            "start_times": ["02:00", "03:15", "04:30"],
            "id": "b",
            "budget": 100,
            "group_run_times": [
                {
                    "device_id": "test-device-123",
                    "run_times": [{"run_time": 75, "station": 2}],
                }
            ],
            "is_smart_program": True,
            "device_id": "test-device-123",
            "program": "e",
            "run_times": [{"run_time": 75, "station": 2}],
            "enabled": True,
            "created_at": "2026-08-29T21:00:00.000Z",
        },
    }


@pytest.fixture
def mock_sprinkler_device_with_next_start_time() -> BHyveDevice:
    """Mock BHyve sprinkler device with next_start_time in device status."""
    return BHyveDevice(
        {
            "id": "test-device-123",
            "name": "Test Sprinkler",
            "type": "sprinkler_timer",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "hardware_version": "v2.0",
            "firmware_version": "1.2.3",
            "is_connected": True,
            "status": {
                "run_mode": "auto",
                "watering_status": None,
                "next_start_time": "2026-05-01T03:30:00-07:00",
                "next_start_programs": ["e"],
            },
            "zones": [{"station": "1", "name": "Front Lawn"}],
        }
    )


@pytest.fixture
def mock_sprinkler_device_no_schedule() -> BHyveDevice:
    """Mock BHyve sprinkler device with no upcoming schedule."""
    return BHyveDevice(
        {
            "id": "test-device-123",
            "name": "Test Sprinkler",
            "type": "sprinkler_timer",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "hardware_version": "v2.0",
            "firmware_version": "1.2.3",
            "is_connected": True,
            "status": {
                "run_mode": "auto",
                "watering_status": None,
            },
            "zones": [{"station": "1", "name": "Front Lawn"}],
        }
    )


class TestBHyveBatterySensor:
    """Test BHyveBatterySensor entity."""

    async def test_battery_sensor_initialization(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test battery sensor entity initialization."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_with_battery, SENSOR_TYPES_BATTERY[0]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            description=description,
        )

        # Test basic properties
        assert sensor.name == "Battery level"
        assert sensor.device_class == SensorDeviceClass.BATTERY
        assert sensor.entity_description.state_class == SensorStateClass.MEASUREMENT
        assert sensor.entity_description.native_unit_of_measurement == PERCENTAGE
        assert sensor.entity_description.entity_category == EntityCategory.DIAGNOSTIC

    async def test_battery_sensor_state(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test battery sensor state and attributes."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_with_battery, SENSOR_TYPES_BATTERY[0]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            description=description,
        )

        # Test state
        assert sensor.native_value == TEST_BATTERY_LEVEL
        assert sensor.available is True

        # Test icon changes based on battery level
        assert sensor.icon is not None
        assert "battery" in sensor.icon

    async def test_battery_sensor_websocket_event(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test battery sensor response to websocket events."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_with_battery, SENSOR_TYPES_BATTERY[0]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            description=description,
        )

        # Initial state
        assert sensor.native_value == TEST_BATTERY_LEVEL

        # Simulate coordinator update with new battery level
        coordinator.data["devices"]["test-device-123"]["device"]["battery"][
            "percent"
        ] = TEST_BATTERY_LEVEL_UPDATED

        # State should be updated
        assert sensor.native_value == TEST_BATTERY_LEVEL_UPDATED


class TestBHyveStateSensor:
    """Test BHyveStateSensor entity."""

    async def test_state_sensor_initialization(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test state sensor entity initialization."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_with_battery, SENSOR_TYPES_SPRINKLER[0]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            description=description,
        )

        # Test basic properties
        assert sensor.name == "State"
        assert sensor.entity_description.entity_category == EntityCategory.DIAGNOSTIC

    async def test_state_sensor_values(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test state sensor with different run modes."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_with_battery, SENSOR_TYPES_SPRINKLER[0]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            description=description,
        )

        # Test initial state
        assert sensor.native_value == "auto"

        # Simulate coordinator update
        coordinator.data["devices"]["test-device-123"]["device"]["status"][
            "run_mode"
        ] = "manual"

        assert sensor.native_value == "manual"


class TestBHyveTemperatureSensor:
    """Test BHyveTemperatureSensor entity."""

    async def test_temperature_sensor_initialization(
        self,
        mock_flood_device: BHyveDevice,
    ) -> None:
        """Test temperature sensor entity initialization."""
        coordinator = create_mock_coordinator(
            {
                "test-flood-456": {
                    "device": mock_flood_device,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_flood_device, SENSOR_TYPES_FLOOD[0]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_flood_device,
            description=description,
        )

        # Test basic properties
        assert sensor.name == "Temperature sensor"
        assert sensor.device_class == SensorDeviceClass.TEMPERATURE
        assert sensor.entity_description.state_class == SensorStateClass.MEASUREMENT
        assert (
            sensor.entity_description.native_unit_of_measurement
            == UnitOfTemperature.FAHRENHEIT
        )

    async def test_temperature_sensor_state(
        self,
        mock_flood_device: BHyveDevice,
    ) -> None:
        """Test temperature sensor state and attributes."""
        coordinator = create_mock_coordinator(
            {
                "test-flood-456": {
                    "device": mock_flood_device,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_flood_device, SENSOR_TYPES_FLOOD[0]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_flood_device,
            description=description,
        )

        # Test state
        assert sensor.native_value == TEST_TEMPERATURE_FAHRENHEIT
        assert sensor.available is True

        # Test attributes
        attrs = sensor.extra_state_attributes
        assert attrs["location"] == "Basement"


class TestBHyveZoneHistorySensor:
    """Test BHyveZoneHistorySensor entity."""

    async def test_zone_history_sensor_initialization(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test zone history sensor entity initialization."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        zone = {"station": "1", "name": "Front Lawn"}

        # Create description for the zone
        description = SensorEntityDescription(
            key="zone_history",
            translation_key="zone_history",
            icon="mdi:history",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

        sensor = BHyveZoneHistorySensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            zone=zone,
            zone_name="Front Lawn",
            description=description,
        )

        # Test basic properties
        assert sensor._attr_name == "Front Lawn zone history"
        assert sensor._attr_translation_placeholders == {"zone_name": "Front Lawn"}
        assert sensor.device_class == SensorDeviceClass.TIMESTAMP
        assert sensor.entity_description.entity_category == EntityCategory.DIAGNOSTIC

    async def test_zone_history_sensor_attributes(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
        mock_zone_history_data: list,
    ) -> None:
        """Test zone history sensor with history data."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": mock_zone_history_data,
                    "landscapes": {},
                }
            }
        )

        zone = {"station": "1", "name": "Front Lawn"}

        # Create description for the zone
        description = SensorEntityDescription(
            key="zone_history",
            translation_key="zone_history",
            icon="mdi:history",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

        sensor = BHyveZoneHistorySensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            zone=zone,
            zone_name="Front Lawn",
            description=description,
        )

        # Test state (should be a datetime object for TIMESTAMP device class)
        assert sensor.native_value is not None
        assert sensor.native_value.year == 2020
        assert sensor.native_value.month == 1
        assert sensor.native_value.day == 9

        # Test attributes
        attrs = sensor.extra_state_attributes
        assert attrs["budget"] == 100
        assert attrs["program"] == "a"
        assert attrs["program_name"] == "Morning Schedule"
        assert attrs["run_time"] == 15
        assert attrs["status"] == "complete"
        assert attrs["consumption_gallons"] == 25.5
        assert attrs["consumption_litres"] == 96.52

    async def test_zone_history_sensor_picks_greatest_start_time(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """
        Selection is by greatest start_time across all irrigation entries.

        Skipped runs are not filtered — they still report consumption. The
        latest entry by timestamp wins regardless of array position or which
        history item it lives in.
        """
        history = [
            {
                "irrigation": [
                    {
                        "station": "1",
                        "budget": 100,
                        "program": "e",
                        "program_name": "Smart Watering",
                        "run_time": 24,
                        "status": "complete",
                        "water_volume_gal": None,
                        "start_time": "2026-04-18T20:00:00.000Z",
                    },
                    {
                        "station": "1",
                        "budget": 100,
                        "program": "manual",
                        "program_name": "manual",
                        "run_time": 0.97,
                        "status": "skipped",
                        "water_volume_gal": 2,
                        "start_time": "2026-04-19T04:36:14.000Z",
                    },
                ]
            },
            {
                "irrigation": [
                    {
                        "station": "1",
                        "budget": 100,
                        "program": "e",
                        "program_name": "Smart Watering",
                        "run_time": 22,
                        "status": "complete",
                        "water_volume_gal": 69,
                        "start_time": "2026-04-16T20:00:04.000Z",
                    }
                ]
            },
        ]
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": history,
                    "landscapes": {},
                }
            }
        )

        description = SensorEntityDescription(
            key="zone_history",
            translation_key="zone_history",
            icon="mdi:history",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        sensor = BHyveZoneHistorySensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            zone={"station": "1", "name": "Front Lawn"},
            zone_name="Front Lawn",
            description=description,
        )

        # Greatest start_time is the 2026-04-19 manual skipped run.
        assert sensor.native_value is not None
        assert sensor.native_value.day == 19
        assert sensor.native_value.hour == 4

        attrs = sensor.extra_state_attributes
        assert attrs["program"] == "manual"
        assert attrs["status"] == "skipped"
        assert attrs["run_time"] == 0.97
        assert attrs["consumption_gallons"] == 2
        assert attrs["consumption_litres"] == 7.57


class TestBHyveSmartWateringZoneSensor:
    """Test BHyveSmartWateringZoneSensor entity."""

    async def test_smart_watering_zone_sensor_initialization(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test smart watering zone sensor entity initialization."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        zone = {"station": "1", "name": "Front Lawn"}

        # Create description for the zone
        description = SensorEntityDescription(
            key="smart_watering_zone",
            translation_key="smart_watering_zone",
            icon="mdi:water-percent",
            device_class=SensorDeviceClass.MOISTURE,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

        sensor = BHyveSmartWateringZoneSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            zone=zone,
            zone_name="Front Lawn",
            description=description,
        )

        # Test basic properties
        assert sensor._attr_name == "Front Lawn smart watering"
        assert sensor._attr_translation_placeholders == {"zone_name": "Front Lawn"}
        assert sensor.device_class == SensorDeviceClass.MOISTURE
        assert sensor.entity_description.entity_category == EntityCategory.DIAGNOSTIC

    async def test_smart_watering_zone_sensor_attributes(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
        mock_smart_watering_landscapes_data: dict,
        mock_smart_watering_programs_data: dict,
    ) -> None:
        """Test smart watering zone sensor with landscape and zone forecast data."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": mock_smart_watering_landscapes_data,
                }
            },
            mock_smart_watering_programs_data,
        )

        # Create description for the zone
        description = SensorEntityDescription(
            key="smart_watering_zone",
            translation_key="smart_watering_zone",
            icon="mdi:water-percent",
            device_class=SensorDeviceClass.MOISTURE,
            entity_category=EntityCategory.DIAGNOSTIC,
        )

        sensor = BHyveSmartWateringZoneSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            zone={"station": 2, "name": "Front Lawn"},
            zone_name="Front Lawn",
            description=description,
        )

        # Pre 9am - Test state based on initial water level plus rainfall and irrigation
        with patch.object(
            BHyveSmartWateringZoneSensor, "_get_local_datetime"
        ) as mock_get_local_datetime:
            mock_get_local_datetime.return_value = datetime(
                2026, 8, 30, 2, 00, tzinfo=UTC
            )
            assert sensor.native_value == 100
            assert (
                sensor.extra_state_attributes["current_moisture_balance"]
                == 2.5034046142773994 + 0.2 + 0.3
            )

        # 9am - Test state based on initial water level plus rainfall and irrigation
        # minus 0% evapotranspiration
        with patch.object(
            BHyveSmartWateringZoneSensor, "_get_local_datetime"
        ) as mock_get_local_datetime:
            mock_get_local_datetime.return_value = datetime(
                2026, 8, 30, 9, 00, tzinfo=UTC
            )
            assert sensor.native_value == 100
            assert (
                sensor.extra_state_attributes["current_moisture_balance"]
                == 2.5034046142773994 + 0.2 + 0.3
            )

        # 3pm - Test state based on initial water level plus rainfall and irrigation
        # minus 50% evapotranspiration
        with patch.object(
            BHyveSmartWateringZoneSensor, "_get_local_datetime"
        ) as mock_get_local_datetime:
            mock_get_local_datetime.return_value = datetime(
                2026, 8, 30, 15, 00, tzinfo=UTC
            )
            assert sensor.native_value == 100
            assert sensor.extra_state_attributes[
                "current_moisture_balance"
            ] == 2.5034046142773994 + 0.2 + 0.3 - (0.19325470937656308 * 0.8 * 0.5)

        # 9 pm - Test state based on final water level
        with patch.object(
            BHyveSmartWateringZoneSensor, "_get_local_datetime"
        ) as mock_get_local_datetime:
            mock_get_local_datetime.return_value = datetime(
                2026, 8, 30, 22, 00, tzinfo=UTC
            )
            assert sensor.native_value == 31
            assert (
                sensor.extra_state_attributes["current_moisture_balance"]
                == 2.348800846776149
            )

        # Post 9pm - Test state based on final water level
        with patch.object(
            BHyveSmartWateringZoneSensor, "_get_local_datetime"
        ) as mock_get_local_datetime:
            mock_get_local_datetime.return_value = datetime(
                2026, 8, 30, 22, 00, tzinfo=UTC
            )
            assert sensor.native_value == 31
            assert (
                sensor.extra_state_attributes["current_moisture_balance"]
                == 2.348800846776149
            )

        # Test fixed attributes
        with patch.object(
            BHyveSmartWateringZoneSensor, "_get_local_datetime"
        ) as mock_get_local_datetime:
            mock_get_local_datetime.return_value = datetime(
                2026, 8, 30, 12, 00, tzinfo=UTC
            )
            attrs = sensor.extra_state_attributes
            assert attrs["application_rate"] == 0.5727296703296705
            assert attrs["efficiency"] == 0.5845321186787661
            assert attrs["plant_factor"] == 0.8
            assert attrs["micro_climate"] == 1
            assert attrs["max_allowable_depletion"] == 0.35
            assert attrs["field_capacity"] == 0.43
            assert attrs["permanent_wilting_point"] == 0.27
            assert attrs["root_depth"] == 6
            assert attrs["allowable_soil_acc"] == 0.16
            assert attrs["infiltration_rate"] == 0.15
            assert attrs["rainfall_efficiency"] == 0.4
            assert attrs["drought_factor"] == 1
            assert attrs["available_water"] == 0.15999999999999998
            assert attrs["field_capacity_depth"] == 2.58
            assert attrs["pwp_depth"] == 1.62
            assert attrs["plant_available_water"] == 0.96
            assert attrs["readily_available_water"] == 0.33599999999999997
            assert attrs["replenishment_point"] == 2.244
            assert attrs["max_runtime"] == 22
            assert attrs["landscape_coefficient"] == 0.8
            assert attrs["etc"] == 0.1546037675012505
            assert attrs["eto"] == 0.19325470937656308
            assert attrs["standard_runtime"] == 60


class TestSensorWebsocketEvents:
    """Test sensor response to websocket events."""

    async def test_sensors_handle_device_connection_events(
        self,
        mock_sprinkler_device_with_battery: BHyveDevice,
    ) -> None:
        """Test sensors handle device connection/disconnection events."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_battery,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        battery_description = create_sensor_description(
            mock_sprinkler_device_with_battery, SENSOR_TYPES_BATTERY[0]
        )
        battery_sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            description=battery_description,
        )

        state_description = create_sensor_description(
            mock_sprinkler_device_with_battery, SENSOR_TYPES_SPRINKLER[0]
        )
        state_sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_battery,
            description=state_description,
        )

        # Initial state - sensors should be available
        assert battery_sensor.available is True
        assert state_sensor.available is True

        # Simulate device disconnection
        coordinator.data["devices"]["test-device-123"]["device"]["is_connected"] = False

        # Sensors should be unavailable
        assert battery_sensor.available is False
        assert state_sensor.available is False


class TestBHyveNextWateringSensor:
    """Test next watering device-level sensor (SENSOR_TYPES_SPRINKLER[1])."""

    async def test_next_watering_sensor_initialization(
        self,
        mock_sprinkler_device_with_next_start_time: BHyveDevice,
    ) -> None:
        """Test next watering sensor entity initialization."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_next_start_time,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_with_next_start_time, SENSOR_TYPES_SPRINKLER[1]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_next_start_time,
            description=description,
        )

        assert sensor.name == "Next watering"
        assert sensor.device_class == SensorDeviceClass.TIMESTAMP
        assert sensor._attr_unique_id.endswith(":next_watering")

    async def test_next_watering_sensor_with_scheduled_time(
        self,
        mock_sprinkler_device_with_next_start_time: BHyveDevice,
    ) -> None:
        """Test next watering sensor returns correct timestamp and programs."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_with_next_start_time,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_with_next_start_time, SENSOR_TYPES_SPRINKLER[1]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_with_next_start_time,
            description=description,
        )

        # Value should parse to a datetime
        assert sensor.native_value is not None
        assert sensor.native_value.year == 2026
        assert sensor.native_value.month == 5
        assert sensor.native_value.day == 1

        # Programs attribute should be present when next_start_programs exists
        attrs = sensor.extra_state_attributes
        assert attrs["programs"] == ["e"]

    async def test_next_watering_sensor_no_schedule(
        self,
        mock_sprinkler_device_no_schedule: BHyveDevice,
    ) -> None:
        """Test next watering sensor returns None when next_start_time is absent."""
        coordinator = create_mock_coordinator(
            {
                "test-device-123": {
                    "device": mock_sprinkler_device_no_schedule,
                    "history": [],
                    "landscapes": {},
                }
            }
        )

        description = create_sensor_description(
            mock_sprinkler_device_no_schedule, SENSOR_TYPES_SPRINKLER[1]
        )
        sensor = BHyveSensor(
            coordinator=coordinator,
            device=mock_sprinkler_device_no_schedule,
            description=description,
        )

        # No next_start_time in status — should return None (HA renders as Unknown)
        assert sensor.native_value is None
        # No programs attribute when there is no schedule
        assert sensor.extra_state_attributes == {}
