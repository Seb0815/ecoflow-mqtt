from custom_components.ecoflow_cloud.api import EcoflowApiClient
from custom_components.ecoflow_cloud.devices import const, BaseDevice
from custom_components.ecoflow_cloud.entities import BaseSensorEntity, BaseNumberEntity, BaseSwitchEntity, \
    BaseSelectEntity

# Verwende Sensor-Klassen mit Docker-Fallback
from custom_components.ecoflow_cloud.sensor import (
    WattsSensorEntity, LevelSensorEntity, CapacitySensorEntity, 
    InWattsSensorEntity, OutWattsSensorEntity, RemainSensorEntity, 
    MilliVoltSensorEntity, TempSensorEntity, CyclesSensorEntity, 
    EnergySensorEntity, CumulativeCapacitySensorEntity,
    extract_sensor_parameters_from_device_class, HOMEASSISTANT_AVAILABLE
)

# Docker-kompatibles DateTime-Import
try:
    from homeassistant.util import utcnow
except ImportError:
    from datetime import datetime, timezone
    def utcnow():
        return datetime.now(timezone.utc)

import logging

_LOGGER = logging.getLogger(__name__)

class StreamAC(BaseDevice):
    _parameter_analysis_done = False  # Klassenweite Variable für einmalige Analyse
    
    def sensors(self, client: EcoflowApiClient) -> list[BaseSensorEntity]:
        return [
            # "accuChgCap": 198511,
            CumulativeCapacitySensorEntity(client, self, "accuChgCap", const.ACCU_CHARGE_CAP, False),
            # "accuChgEnergy": 3992,
            EnergySensorEntity(client, self, "accuChgEnergy", const.ACCU_CHARGE_ENERGY, False),
            # "accuDsgCap": 184094,
            CumulativeCapacitySensorEntity(client, self, "accuDsgCap", const.ACCU_DISCHARGE_CAP, False),
            # "accuDsgEnergy": 3646,
            EnergySensorEntity(client, self, "accuDsgEnergy", const.ACCU_DISCHARGE_ENERGY, False),
            # "actSoc": 46.0,
            # "amp": 44671,
            # "backupReverseSoc": 5,
            # "balanceCmd": 0,
            # "balanceState": 0,
            # "bmsAlarmState1": 0,
            # "bmsAlarmState2": 0,
            # "bmsBattHeating": false,
            # "bmsBattSoc": 46.0,
            # "bmsBattSoh": 100.0,
            # "bmsChgDsgState": 2,
            # "bmsChgRemTime": 88,
            RemainSensorEntity(client, self, "bmsChgRemTime", const.CHARGE_REMAINING_TIME, False),
            # "bmsDesignCap": 1920,
            # "bmsDsgRemTime": 5939,
            RemainSensorEntity(client, self, "bmsDsgRemTime", const.DISCHARGE_REMAINING_TIME, False),
            # "bmsFault": 0,
            # "bmsFaultState": 0,
            # "bmsHeartbeatVer": 260,
            # "bmsMaxCellTemp": 35,
            # "bmsMaxMosTemp": 47,
            # "bmsMinCellTemp": 33,
            # "bmsMinMosTemp": 47,
            # "bmsProtectState1": 0,
            # "bmsProtectState2": 0,
            # "bmsSn": "BKxxxx",
            # "bqSysStatReg": 0,
            # "brightness": 100,
            # "busbarPowLimit": 2300,
            # "calendarSoh": 88.0,
            # "cellId": 2,
            # "cellNtcNum": 2,
            # "cellSeriesNum": 6,
            # "chgDsgState": 2,
            # "cloudMetter.hasMeter": true,
            # "cloudMetter.model": "CT_EF_01",
            # "cloudMetter.phaseAPower": -134,
            # "cloudMetter.phaseBPower": 0,
            # "cloudMetter.phaseCPower": 0,
            # "cloudMetter.sn": "BKxxxx",
            # "cmsBattFullEnergy": 3840,
            # "cmsBattPowInMax": 2114,
            # "cmsBattPowOutMax": 2400,
            # "cmsBattSoc": 43.0,
            # "cmsBattSoh": 100.0,
            # "cmsBmsRunState": 1,
            # "cmsChgDsgState": 2,
            # "cmsChgRemTime": 88,
            # "cmsDsgRemTime": 5939,
            # "cmsMaxChgSoc": 100,
            # "cmsMinDsgSoc": 5,
            # "curSensorNtcNum": 0,
            # "curSensorTemp": [],
            # "cycleSoh": 100.0,
            # "cycles": 1,
            CyclesSensorEntity(client, self, "cycles", const.CYCLES,False),
            # "designCap": 100000,
            CapacitySensorEntity(client, self, "designCap", const.STREAM_DESIGN_CAPACITY,False),
            # "devCtrlStatus": 1,
            # "devSleepState": 0,
            # "diffSoc": 0.2050476,
            # "displayPropertyFullUploadPeriod": 120000,
            # "displayPropertyIncrementalUploadPeriod": 2000,
            # "distributedDeviceStatus": "MASTER",
            # "ecloudOcv": 65535,
            # "energyBackupState": 0,
            # "energyStrategyOperateMode.operateIntelligentScheduleModeOpen": false,
            # "energyStrategyOperateMode.operateScheduledOpen": false,
            # "energyStrategyOperateMode.operateSelfPoweredOpen": true,
            # "energyStrategyOperateMode.operateTouModeOpen": false,
            # "f32ShowSoc": 46.317574,
            LevelSensorEntity(client, self, "f32ShowSoc", const.STREAM_POWER_BATTERY_SOC,False),
            # "feedGridMode": 2,
            # "feedGridModePowLimit": 800,
            # "feedGridModePowMax": 800,
            # "fullCap": 100000,
            CapacitySensorEntity(client, self, "fullCap", const.STREAM_FULL_CAPACITY, False),
            # "gridCodeSelection": "GRID_STD_CODE_UTE_MAINLAND",
            # "gridCodeVersion": 10001,
            # "gridConnectionFreq": 49.974655,
            # "gridConnectionPower": -967.2364,
            WattsSensorEntity(client, self, "gridConnectionPower", const.STREAM_POWER_AC),
            # "gridConnectionSta": "PANEL_GRID_IN",
            # "gridConnectionVol": 235.34576,
            MilliVoltSensorEntity(client, self, "gridConnectionVol", const.STREAM_POWER_VOL, False),
            # "gridSysDeviceCnt": 2,
            # "heatfilmNtcNum": 0,
            # "heatfilmTemp": [],
            # "hwVer": "V0.0.0",
            # "inputWatts": 900,
            InWattsSensorEntity(client, self, "inputWatts", const.STREAM_IN_POWER, False),
            # "invNtcTemp3": 49,
            # "maxBpInput": 1050,
            # "maxBpOutput": 1200,
            # "maxCellTemp": 35,
            TempSensorEntity(client, self, "maxCellTemp", const.MAX_CELL_TEMP, False),
            # "maxCellVol": 3362,
            MilliVoltSensorEntity(client, self, "maxCellVol", const.MAX_CELL_VOLT, False),
            # "maxCurSensorTemp": 0,
            # "maxEnvTemp": 0,
            # "maxHeatfilmTemp": 0,
            # "maxInvInput": 1200,
            # "maxInvOutput": 1200,
            # "maxMosTemp": 47,
            # "maxVolDiff": 5,
            # "mcuPinInStatus": 0,
            # "mcuPinOutStatus": 0,
            # "minCellTemp": 33,
            TempSensorEntity(client, self, "minCellTemp", const.MIN_CELL_TEMP, False),
            # "minCellVol": 3357,
            MilliVoltSensorEntity(client, self, "minCellVol", const.MIN_CELL_VOLT, False),
            # "minCurSensorTemp": 0,
            # "minEnvTemp": 0,
            # "minHeatfilmTemp": 0,
            # "minMosTemp": 47,
            # "moduleWifiRssi": -22.0,
            # "mosNtcNum": 1,
            # "mosState": 3,
            # "num": 0,
            # "openBmsFlag": 1,
            # "outputWatts": 0,
            OutWattsSensorEntity(client, self, "outputWatts", const.STREAM_OUT_POWER, False),
            # "packSn": "BKxxxxx",
            # "plugInInfoPv2Amp": 0.0,
            # "plugInInfoPv2Flag": false,
            # "plugInInfoPv2Vol": 0.0,
            # "plugInInfoPv3Amp": 0.0,
            # "plugInInfoPv3Flag": false,
            # "plugInInfoPv3Vol": 0.0,
            # "plugInInfoPv4Amp": 0.0,
            # "plugInInfoPv4Flag": false,
            # "plugInInfoPv4Vol": 0.0,
            # "plugInInfoPvAmp": 0.0,
            # "plugInInfoPvFlag": false,
            # "plugInInfoPvVol": 0.0,
            # "powConsumptionMeasurement": 2,
            # "powGetBpCms": 1915.0862,
            WattsSensorEntity(client, self, "powGetBpCms", const.STREAM_POWER_BATTERY),
            # "powGetPv": 0.0,
            WattsSensorEntity(client, self, "powGetPv", const.STREAM_POWER_PV_1, False, True),
            # "powGetPv2": 0.0,
            WattsSensorEntity(client, self, "powGetPv2", const.STREAM_POWER_PV_2, False, True),
            # "powGetPv3": 0.0,
            WattsSensorEntity(client, self, "powGetPv3", const.STREAM_POWER_PV_3, False, True),
            # "powGetPv4": 0.0,
            WattsSensorEntity(client, self, "powGetPv4", const.STREAM_POWER_PV_4, False, True),
            # "powGetPvSum": 2051.3975,
            WattsSensorEntity(client, self, "powGetPvSum", const.STREAM_POWER_PV_SUM),
            
            # PV String Power - Individual String Values (from CMD 22 HeaderStream)
            WattsSensorEntity(client, self, "pv_power_string_1", const.STREAM_POWER_PV_1, False, True),
            WattsSensorEntity(client, self, "pv_power_string_2", const.STREAM_POWER_PV_2, False, True),
            WattsSensorEntity(client, self, "pv_power_string_3", const.STREAM_POWER_PV_3, False, True),
            WattsSensorEntity(client, self, "pv_power_string_4", const.STREAM_POWER_PV_4, False, True),
            
            # PV Candidates - BESTÄTIGTE Kandidaten aus Debug-Logs (alle ~9-11W)
            WattsSensorEntity(client, self, "pv1_candidate_42", const.STREAM_POWER_PV_1, False, True),      # CMD 50 Field 42 = 10.0W - BESTÄTIGT!
            WattsSensorEntity(client, self, "pv2_candidate_44", const.STREAM_POWER_PV_2, False, True),      # CMD 50 Field 44 ~11W - BESTÄTIGT!
            WattsSensorEntity(client, self, "pv3_candidate_6", const.STREAM_POWER_PV_3, False, True),       # CMD 50 Field 6 = 9W - BESTÄTIGT!
            WattsSensorEntity(client, self, "pv4_candidate_14", const.STREAM_POWER_PV_4, False, True),      # CMD 50 Field 14 = 9W - BESTÄTIGT!
            WattsSensorEntity(client, self, "pv_candidate_1424", const.STREAM_POWER_PV_1, False, True),     # CMD 22 Field 1424 = 11W - BESTÄTIGT!
            
            # "powGetSchuko1": 0.0,
            WattsSensorEntity(client, self, "powGetSchuko1", const.STREAM_GET_SCHUKO1, False, True),
            # "powGetSchuko2": 18.654325,
            WattsSensorEntity(client, self, "powGetSchuko2", const.STREAM_GET_SCHUKO2, False, True),
            # "powGetSysGrid": -135.0,
            WattsSensorEntity(client, self, "powGetSysGrid", const.STREAM_POWER_GRID),
            # "powGetSysLoad": 0.0,
            WattsSensorEntity(client, self, "powGetSysLoad", const.STREAM_GET_SYS_LOAD),
            # "powGetSysLoadFromBp": 0.0,
            WattsSensorEntity(client, self, "powGetSysLoadFromBp", const.STREAM_GET_SYS_LOAD_FROM_BP),
            # "powGetSysLoadFromGrid": 0.0,
            WattsSensorEntity(client, self, "powGetSysLoadFromGrid", const.STREAM_GET_SYS_LOAD_FROM_GRID),
            # "powGetSysLoadFromPv": 0.0,
            WattsSensorEntity(client, self, "powGetSysLoadFromPv", const.STREAM_GET_SYS_LOAD_FROM_PV),
            # "powSysAcInMax": 4462,
            # "powSysAcOutMax": 800,
            # "productDetail": 5,
            # "productType": 58,
            # "realSoh": 100.0,
            LevelSensorEntity(client, self, "realSoh", const.REAL_SOH, False),
            # "relay1Onoff": true,
            # "relay2Onoff": true,
            # "relay3Onoff": true,
            # "relay4Onoff": true,
            # "remainCap": 46317,
            CapacitySensorEntity(client, self, "remainCap", const.STREAM_REMAIN_CAPACITY,False),
            # "remainTime": 88,
            RemainSensorEntity(client, self, "remainTime", const.REMAINING_TIME, False),
            # "runtimePropertyFullUploadPeriod": 120000,
            # "runtimePropertyIncrementalUploadPeriod": 2000,
            # "seriesConnectDeviceId": 1,
            # "seriesConnectDeviceStatus": "MASTER",
            
            # HAUPT-SOC aus CMD 50 Field 25 - der echte SOC-Wert für MQTT
            LevelSensorEntity(client, self, "soc", const.STREAM_POWER_BATTERY_SOC, False)   # Field 25: Echter SOC-Wert
            .attr("designCap", const.ATTR_DESIGN_CAPACITY, 0)
            .attr("fullCap", const.ATTR_FULL_CAPACITY, 0)
            .attr("remainCap", const.ATTR_REMAIN_CAPACITY, 0),
            
            # SOC-Parameter aus Champ_cmd21_3 (CMD 21)
            LevelSensorEntity(client, self, "f32ShowSoc_cmd21", const.STREAM_POWER_BATTERY_SOC, False),          # Field 100 - Haupt-SOC!
            LevelSensorEntity(client, self, "soc_cmd21", const.STREAM_POWER_BATTERY_SOC, False),                # Field 101 - SOC Integer 
            LevelSensorEntity(client, self, "bmsBattSoc", const.STREAM_POWER_BATTERY_SOC, False),         # Field 102 - BMS SOC
            LevelSensorEntity(client, self, "actSoc", const.STREAM_POWER_BATTERY_SOC, False),             # Field 103 - Active SOC
            LevelSensorEntity(client, self, "cmsBattSoc", const.STREAM_POWER_BATTERY_SOC, False),         # Field 104 - CMS SOC
            LevelSensorEntity(client, self, "targetSoc", const.STREAM_POWER_BATTERY_SOC, False),          # Field 105 - Target SOC
            LevelSensorEntity(client, self, "diffSoc", const.STREAM_POWER_BATTERY_SOC, False),            # Field 106 - SOC Difference
            LevelSensorEntity(client, self, "Champ_cmd21_3_field460", const.STREAM_POWER_BATTERY_SOC, False), # Field 460 - Potentieller SOC
            
             
            # "socketMeasurePower": 0.0,
            # "soh": 100,
            LevelSensorEntity(client, self, "soh", const.SOH, False),
            # "stormPatternEnable": false,
            # "stormPatternEndTime": 0,
            # "stormPatternOpenFlag": false,
            # "sysGridConnectionPower": -2020.0437,
            WattsSensorEntity(client, self, "sysGridConnectionPower", const.STREAM_POWER_AC_SYS, False),
            # "sysLoaderVer": 4294967295,
            # "sysState": 3,
            # "sysVer": 33620026,
            # "systemGroupId": 12356789,
            # "systemMeshId": 1,
            # "tagChgAmp": 50000,
            # "targetSoc": 46.314102,
            # "temp": 35,
            TempSensorEntity(client, self, "temp", const.BATTERY_TEMP, False)
            .attr("minCellTemp", const.ATTR_MIN_CELL_TEMP, 0)
            .attr("maxCellTemp", const.ATTR_MAX_CELL_TEMP, 0),
            # "v1p0.bmsModel": 1,
            # "v1p0.bmsWarningState": 0,
            # "v1p0.chgAmp": 90000,
            # "v1p0.chgCmd": 1,
            # "v1p0.chgRemainTime": 88,
            # "v1p0.chgState": 2,
            # "v1p0.chgVol": 22158,
            # "v1p0.dsgCmd": 1,
            # "v1p0.dsgRemainTime": 5939,
            # "v1p0.emsIsNormalFlag": 1,
            # "v1p0.f32LcdShowSoc": 46.313,
            # "v1p0.fanLevel": 0,
            # "v1p0.lcdShowSoc": 46,
            # "v1p0.maxAvailableNum": 1,
            # "v1p0.maxChargeSoc": 100,
            # "v1p0.maxCloseOilEbSoc": 100,
            # "v1p0.minDsgSoc": 5,
            # "v1p0.minOpenOilEbSoc": 20,
            # "v1p0.openBmsIdx": 1,
            # "v1p0.openUpsFlag": 1,
            # "v1p0.paraVolMax": 0,
            # "v1p0.paraVolMin": 0,
            # "v1p3.chgDisableCond": 0,
            # "v1p3.chgLinePlugInFlag": 0,
            # "v1p3.dsgDisableCond": 0,
            # "v1p3.emsHeartbeatVer": 259,
            # "v1p3.sysChgDsgState": 2,
            # "vol": 20161,
            MilliVoltSensorEntity(client, self, "vol", const.BATTERY_VOLT, False)
            .attr("minCellVol", const.ATTR_MIN_CELL_VOLT, 0)
            .attr("maxCellVol", const.ATTR_MAX_CELL_VOLT, 0),
            # "waterInFlag": 0,

        ]
    # moduleWifiRssi
    def numbers(self, client: EcoflowApiClient) -> list[BaseNumberEntity]:
        return []

    def switches(self, client: EcoflowApiClient) -> list[BaseSwitchEntity]:
        return []

    def selects(self, client: EcoflowApiClient) -> list[BaseSelectEntity]:
        return []
    
    @classmethod
    def get_defined_parameters(cls) -> set:
        """
        Extrahiert alle definierten Parameter aus dieser Device-Klasse
        Diese Methode kann ohne Client-Instanz aufgerufen werden
        """
        return extract_sensor_parameters_from_device_class(cls)

    def _prepare_data_get_topic(self, raw_data) -> dict[str, any]:
        return super()._prepare_data(raw_data)

    def _prepare_data(self, raw_data) -> dict[str, any]:
        raw = {"params": {}}
        from .proto import ecopacket_pb2 as ecopacket, stream_ac_pb2 as stream_ac, stream_ac_pb2 as stream_ac2
        try:
            payload =raw_data

            while True:
                _LOGGER.debug("payload \"%s\"", payload.hex())
                packet = stream_ac.SendHeaderStreamMsg()
                packet.ParseFromString(payload)

                if hasattr(packet.msg, "pdata") :
                    _LOGGER.debug("cmd id \"%u\" fct id \"%u\" content \"%s\" - pdata:\"%s\"", packet.msg.cmd_id, packet.msg.cmd_func, str(packet), str(packet.msg.pdata.hex()))
                else :
                    _LOGGER.debug("cmd id \"%u\" fct id \"%u\" content \"%s\"", packet.msg.cmd_id, str(packet))

                if packet.msg.cmd_id < 0: #packet.msg.cmd_id != 21 and packet.msg.cmd_id != 22 and packet.msg.cmd_id != 50:
                    _LOGGER.info("Unsupported EcoPacket cmd id %u", packet.msg.cmd_id)

                else:
                    _LOGGER.debug("new payload \"%s\"",str(packet.msg.pdata.hex()))
                    
                    # Intelligentes Protobuf-Parsing basierend auf cmd_id
                    if packet.msg.cmd_id == 21:
                        # CMD 21: Verwende spezifische Protobuf-Definitionen
                        self._parsedata(packet, stream_ac2.Champ_cmd21(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd21_3(), raw)
                    elif packet.msg.cmd_id == 50:
                        # CMD 50: Verwende spezifische Protobuf-Definitionen  
                        self._parsedata(packet, stream_ac2.Champ_cmd50(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd50_3(), raw)
                    elif packet.msg.cmd_id == 22:
                        # CMD 22: Versuche alle Definitionen (häufig für Status-Updates)
                        self._parsedata(packet, stream_ac2.HeaderStream(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd21(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd50(), raw)
                    else:
                        # Unbekannte CMD ID: Versuche alle Definitionen
                        _LOGGER.debug("Unknown cmd_id %u, trying all protobuf definitions", packet.msg.cmd_id)
                        self._parsedata(packet, stream_ac2.HeaderStream(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd21(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd21_3(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd50(), raw)
                        self._parsedata(packet, stream_ac2.Champ_cmd50_3(), raw)

                    fields_found = len(raw["params"])
                _LOGGER.info("Found %u fields", fields_found)
                
                # Debug-System: Analysiere Raw-Protobuf für fehlende Field-Nummern
                self._debug_protobuf_fields(packet, raw["params"])
                
                # Nutze die intelligente Parameter-Analyse aus BaseDevice - nur beim ersten Mal
                if fields_found == 0 and not StreamAC._parameter_analysis_done:
                    _LOGGER.debug("No protobuf fields found, analyzing missing parameters (first time)")
                    analysis = self.analyze_missing_parameters(raw["params"], packet.msg.pdata.hex() if hasattr(packet.msg, "pdata") else payload.hex())
                    
                    # Füge gefundene Kandidaten zu den Parametern hinzu
                    if "hex_candidates" in analysis:
                        for key, candidate_info in analysis["hex_candidates"].items():
                            raw["params"][key] = candidate_info["value"]
                    
                    # Logge Verbesserungsvorschläge
                    if analysis.get("suggestions"):
                        _LOGGER.info("Device class improvement suggestions:")
                        for suggestion in analysis["suggestions"]:
                            _LOGGER.info(f"  - {suggestion}")
                    
                    # Markiere Analyse als abgeschlossen
                    StreamAC._parameter_analysis_done = True
                    _LOGGER.info("Parameter analysis completed for StreamAC - will not repeat")
                
                elif fields_found == 0 and StreamAC._parameter_analysis_done:
                        _LOGGER.debug("No protobuf fields found, but parameter analysis already done - skipping")
                        
                        # Für unbekannte Nachrichtentypen: Basis-Metadaten hinzufügen
                        raw["params"]["unknown_message_type"] = True
                        raw["params"]["payload_size"] = len(packet.msg.pdata) if hasattr(packet.msg, "pdata") else len(payload)
                        raw["params"]["cmd_id"] = packet.msg.cmd_id if hasattr(packet.msg, "cmd_id") else "unknown"
                        raw["params"]["cmd_func"] = packet.msg.cmd_func if hasattr(packet.msg, "cmd_func") else "unknown"
                        
                        # Payload-Analyse für potentielle Patterns
                        if hasattr(packet.msg, "pdata") and len(packet.msg.pdata) > 0:
                            self._analyze_unknown_payload(packet.msg.pdata, raw["params"])

                raw["timestamp"] = utcnow()

                if packet.ByteSize() >= len(payload):
                    break

                _LOGGER.info("Found another frame in payload")

                packet_length = len(payload) - packet.ByteSize()
                payload = payload[:packet_length]

        except Exception as error:
            _LOGGER.error(error)
            _LOGGER.debug("raw_data : \"%s\"  raw_data.hex() : \"%s\"",str(raw_data),str(raw_data.hex()))
        
        # Filter: Entferne field_xxxx Parameter von der MQTT-Übertragung (bleiben im Log)
        filtered_params = {}
        field_params_count = 0
        
        for key, value in raw["params"].items():
            # Entferne alle field_xxx und Champ_cmd50_3_fieldX Parameter von MQTT
            if (key.startswith("field_") or 
                key.startswith("Champ_cmd50_3_field") or
                key.startswith("Champ_cmd21_3_field") and key != "Champ_cmd21_3_field460" and key != "Champ_cmd21_3_field602"):
                field_params_count += 1
                _LOGGER.debug(f"🔧 DEBUG-ONLY Parameter (nicht via MQTT): {key} = {value}")
                
               
                continue
            
            # Behalte wichtige, benannte Parameter für MQTT
            filtered_params[key] = value
        
        if field_params_count > 0:
            _LOGGER.info(f"Filtered {field_params_count} debug-only field_xxx parameters from MQTT (kept in logs)")
        
        raw["params"] = filtered_params
        return raw

    def _analyze_unknown_payload(self, payload: bytes, params: dict):
        """Analysiert unbekannte Payloads auf potentielle Patterns und Datenstrukturen"""
        try:
            hex_str = payload.hex()
            
            # Pattern-Analyse
            params["payload_pattern"] = self._identify_payload_pattern(hex_str)
            
            # Entropy-Analyse (verschlüsselt vs. unverschlüsselt)
            entropy = self._calculate_entropy(payload)
            params["payload_entropy"] = round(entropy, 3)
            
            if entropy > 7.5:
                params["likely_encrypted"] = True
                _LOGGER.debug(f"High entropy ({entropy:.3f}) suggests encrypted payload")
            elif entropy < 4.0:
                params["likely_structured"] = True
                _LOGGER.debug(f"Low entropy ({entropy:.3f}) suggests structured data")
            
            # Suche nach repeating patterns
            repeated_patterns = self._find_repeated_patterns(hex_str)
            if repeated_patterns:
                params["repeated_patterns"] = repeated_patterns[:3]  # Top 3
                
            # Byte-Häufigkeitsanalyse
            byte_freq = self._analyze_byte_frequency(payload)
            if byte_freq:
                params["dominant_bytes"] = byte_freq
            
            _LOGGER.debug(f"Unknown payload analysis: pattern={params.get('payload_pattern')}, entropy={entropy:.3f}")
            
        except Exception as e:
            _LOGGER.debug(f"Unknown payload analysis failed: {e}")
            params["analysis_error"] = str(e)

    def _identify_payload_pattern(self, hex_str: str) -> str:
        """Identifiziert bekannte Patterns in Hex-Daten"""
        # Protobuf-typische Patterns
        if hex_str.startswith("08") or hex_str.startswith("0a"):
            return "protobuf_like"
        
        # JSON-ähnliche Patterns (Base64 encoded JSON)
        if hex_str.startswith("7b") or hex_str.startswith("5b"):  # { oder [
            return "json_like"
        
        # Verschlüsselungspatterns
        if len(set(hex_str)) / len(hex_str) > 0.8:  # Hohe Diversität
            return "high_entropy"
        
        # Wiederholende Patterns
        if len(hex_str) > 20:
            first_quarter = hex_str[:len(hex_str)//4]
            if first_quarter in hex_str[len(hex_str)//4:]:
                return "repeating_pattern"
        
        return "unknown"

    def _calculate_entropy(self, data: bytes) -> float:
        """Berechnet die Shannon-Entropie der Daten"""
        if not data:
            return 0.0
        
        # Byte-Häufigkeiten zählen
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        
        # Shannon-Entropie berechnen
        import math
        entropy = 0.0
        data_len = len(data)
        for count in byte_counts.values():
            probability = count / data_len
            if probability > 0:
                entropy -= probability * math.log2(probability)
        
        return entropy

    def _find_repeated_patterns(self, hex_str: str) -> list:
        """Findet wiederholende Patterns in Hex-Strings"""
        patterns = {}
        min_pattern_len = 4  # Mindestens 2 Bytes
        max_pattern_len = min(20, len(hex_str) // 3)  # Maximal 10 Bytes oder 1/3 der Gesamtlänge
        
        for pattern_len in range(min_pattern_len, max_pattern_len + 1, 2):  # Nur gerade Längen
            for i in range(len(hex_str) - pattern_len + 1):
                pattern = hex_str[i:i + pattern_len]
                
                # Zähle Vorkommen
                count = 0
                pos = 0
                while pos < len(hex_str):
                    pos = hex_str.find(pattern, pos)
                    if pos == -1:
                        break
                    count += 1
                    pos += pattern_len
                
                if count >= 3:  # Mindestens 3 Vorkommen
                    patterns[pattern] = count
        
        # Sortiere nach Häufigkeit
        return sorted(patterns.items(), key=lambda x: x[1], reverse=True)

    def _analyze_byte_frequency(self, data: bytes) -> dict:
        """Analysiert Byte-Häufigkeiten für Anomalien"""
        if not data:
            return {}
        
        byte_counts = {}
        for byte in data:
            byte_counts[byte] = byte_counts.get(byte, 0) + 1
        
        # Finde die häufigsten Bytes
        sorted_bytes = sorted(byte_counts.items(), key=lambda x: x[1], reverse=True)
        
        # Interessante Bytes (häufigste und ungewöhnliche)
        result = {}
        if sorted_bytes:
            most_common = sorted_bytes[0]
            result["most_common_byte"] = f"0x{most_common[0]:02x} ({most_common[1]}x)"
            
            # Prüfe auf ungewöhnliche Häufigkeiten
            if most_common[1] > len(data) * 0.3:  # Ein Byte macht >30% aus
                result["anomaly"] = "single_byte_dominance"
        
        return result

    def _debug_protobuf_fields(self, packet, decoded_params: dict):
        """
        Debug-System: Analysiert Raw-Protobuf-Daten, um fehlende Field-Nummern zu identifizieren
        Dieses System hilft dabei, die Protobuf-Definition systematisch zu vervollständigen
        """
        if not hasattr(packet.msg, "pdata") or len(packet.msg.pdata) == 0:
            return
            
        payload = packet.msg.pdata
        cmd_id = packet.msg.cmd_id
        
        _LOGGER.info(f"=== PROTOBUF DEBUG ANALYSIS for CMD {cmd_id} ===")
        _LOGGER.info(f"Payload length: {len(payload)} bytes")
        _LOGGER.info(f"Decoded parameters: {len(decoded_params)}")
        
        # 1. Analysiere alle Protobuf-Fields im Raw-Payload
        protobuf_fields = self._extract_protobuf_fields(payload)
        _LOGGER.info(f"Raw protobuf fields found: {len(protobuf_fields)}")
        
        # 2. Identifiziere fehlende Fields
        decoded_field_numbers = set()
        for field_info in protobuf_fields:
            field_number = field_info['field_number']
            if any(param_name for param_name in decoded_params.keys() 
                   if not param_name.startswith(('unknown_', 'payload_', 'cmd_', 'repeated_', 'dominant_'))):
                # Dieses Field wurde wahrscheinlich dekodiert
                decoded_field_numbers.add(field_number)
        
        missing_fields = [f for f in protobuf_fields if f['field_number'] not in decoded_field_numbers]
        
        if missing_fields:
            _LOGGER.info(f"=== MISSING PROTOBUF FIELDS ({len(missing_fields)}) ===")
            for field_info in missing_fields:
                field_num = field_info['field_number']
                wire_type = field_info['wire_type']
                value = field_info['value']
                wire_type_name = self._get_wire_type_name(wire_type)
                
                _LOGGER.info(f"Field {field_num}: {wire_type_name} = {value}")
                    
        # 3. Generiere Protobuf-Definition-Vorschläge
        if missing_fields:
            _LOGGER.info("=== PROTOBUF DEFINITION SUGGESTIONS ===")
            suggestions = self._generate_protobuf_suggestions(missing_fields, cmd_id)
            for suggestion in suggestions:
                _LOGGER.info(f"  {suggestion}")
        
        # 4. PV-Kandidaten-Suche: Suche nach Werten für PV1-PV4 (alle 10-12W)
        _LOGGER.info("=== PV CANDIDATE SEARCH (PV1-PV4 all at 10-12W) ===")
        pv_candidates_found = 0
        for field_info in protobuf_fields:
            field_num = field_info['field_number']
            value = field_info['value']
            
            # Prüfe auf numerische Werte im PV-Bereich (erweitert auf 8-15W)
            if isinstance(value, (int, float)):
                # PV1-PV4 Bereich: 8-15W (alle aktuell 10-12W)
                if 8 <= value <= 15:
                    pv_candidates_found += 1
                    _LOGGER.info(f"🔍 PV CANDIDATE: Field {field_num} = {value}W (matches PV1-PV4 range 10-12W)")
                
        if pv_candidates_found == 0:
            _LOGGER.info("🔍 No PV candidates found in expected range (8-15W)")
        else:
            _LOGGER.info(f"🔍 Found {pv_candidates_found} PV candidates in expected range (8-15W)")
            
        _LOGGER.info("=== END PROTOBUF DEBUG ANALYSIS ===")

    def _extract_protobuf_fields(self, payload: bytes) -> list:
        """
        Extrahiert alle Protobuf-Fields aus dem Raw-Payload
        """
        fields = []
        pos = 0
        
        while pos < len(payload):
            try:
                # Lese Protobuf-Tag (field_number + wire_type)
                tag, pos = self._read_varint(payload, pos)
                if tag is None:
                    break
                    
                field_number = tag >> 3
                wire_type = tag & 0x07
                
                # Lese Wert basierend auf Wire-Type
                value, pos = self._read_protobuf_value(payload, pos, wire_type)
                if value is not None:
                    fields.append({
                        'field_number': field_number,
                        'wire_type': wire_type,
                        'value': value,
                        'position': pos - len(self._encode_value(value, wire_type))
                    })
                    
            except Exception as e:
                _LOGGER.debug(f"Protobuf parsing stopped at position {pos}: {e}")
                break
                
        return fields

    def _read_varint(self, data: bytes, pos: int) -> tuple:
        """Liest einen Protobuf-Varint"""
        result = 0
        shift = 0
        start_pos = pos
        
        while pos < len(data):
            byte = data[pos]
            result |= (byte & 0x7F) << shift
            pos += 1
            
            if byte & 0x80 == 0:  # MSB ist 0, Ende des Varint
                return result, pos
                
            shift += 7
            if shift >= 64:  # Schutz vor unendlichen Schleifen
                break
                
        return None, start_pos

    def _read_protobuf_value(self, data: bytes, pos: int, wire_type: int) -> tuple:
        """Liest einen Protobuf-Wert basierend auf dem Wire-Type"""
        import struct
        
        try:
            if wire_type == 0:  # Varint
                return self._read_varint(data, pos)
            elif wire_type == 1:  # 64-bit
                if pos + 8 <= len(data):
                    value = struct.unpack('<d', data[pos:pos+8])[0]  # Double
                    return value, pos + 8
            elif wire_type == 2:  # Length-delimited
                length, pos = self._read_varint(data, pos)
                if length is not None and pos + length <= len(data):
                    value = data[pos:pos + length]
                    # Versuche String-Dekodierung
                    try:
                        decoded = value.decode('utf-8')
                        return decoded, pos + length
                    except:
                        return value.hex(), pos + length
            elif wire_type == 5:  # 32-bit
                if pos + 4 <= len(data):
                    value = struct.unpack('<f', data[pos:pos+4])[0]  # Float
                    return value, pos + 4
                    
        except Exception as e:
            _LOGGER.debug(f"Failed to read wire_type {wire_type} at pos {pos}: {e}")
            
        return None, pos

    def _encode_value(self, value, wire_type: int) -> bytes:
        """Hilfsmethod für Längenberechnung"""
        import struct
        if wire_type == 0:  # Varint
            return b'\x00'  # Vereinfacht
        elif wire_type == 1:  # 64-bit
            return b'\x00' * 8
        elif wire_type == 5:  # 32-bit
            return b'\x00' * 4
        elif wire_type == 2:  # Length-delimited
            if isinstance(value, str):
                return value.encode('utf-8')
            return b'\x00'
        return b'\x00'

    def _get_wire_type_name(self, wire_type: int) -> str:
        """Konvertiert Wire-Type-Nummer zu lesbarem Namen"""
        wire_types = {
            0: "varint",
            1: "64-bit",
            2: "length-delimited", 
            3: "start-group",
            4: "end-group",
            5: "32-bit"
        }
        return wire_types.get(wire_type, f"unknown-{wire_type}")

    def _generate_protobuf_suggestions(self, missing_fields: list, cmd_id: int) -> list:
        """
        Generiert konkrete Vorschläge für die Protobuf-Definition
        """
        suggestions = []
        
        # Bestimme welche Message erweitert werden sollte
        if cmd_id == 21:
            message_name = "Champ_cmd21_3"
        elif cmd_id == 22:
            message_name = "HeaderStream"  # oder eine neue Message
        elif cmd_id == 50:
            message_name = "Champ_cmd50_3"
        else:
            message_name = f"Champ_cmd{cmd_id}_new"
            
        suggestions.append(f"// Add to {message_name} message:")
        
        for field_info in missing_fields:
            field_num = field_info['field_number']
            wire_type = field_info['wire_type']
            value = field_info['value']
            
            # Schlage sinnvolle Feldnamen vor
            field_name = self._suggest_field_name(field_info)
            proto_type = self._get_proto_type(wire_type)
            
            suggestions.append(f"optional {proto_type} {field_name} = {field_num};")
                
        return suggestions

    def _suggest_field_name(self, field_info: dict) -> str:
        """Schlägt einen sinnvollen Feldnamen vor"""
        field_num = field_info['field_number']
        wire_type = field_info['wire_type']
        
        # Generische Namen basierend auf Typ
        if wire_type == 5:  # 32-bit float
            return f"float_field_{field_num}"
        elif wire_type == 0:  # varint
            return f"int_field_{field_num}"
        elif wire_type == 2:  # length-delimited
            return f"string_field_{field_num}"
        else:
            return f"field_{field_num}"

    def _get_proto_type(self, wire_type: int) -> str:
        """Konvertiert Wire-Type zu Protobuf-Typ"""
        if wire_type == 0:
            return "uint32"
        elif wire_type == 1:
            return "double"
        elif wire_type == 2:
            return "string"  # oder bytes
        elif wire_type == 5:
            return "float"
        return "bytes"

    def _parsedata(self, packet, content, raw):
        """Verbesserte Protobuf-Parsing-Methode mit detailliertem Debugging"""
        content_type = type(content).__name__
        initial_param_count = len(raw["params"])
        
        try:
            if hasattr(packet.msg, "pdata") and len(packet.msg.pdata) > 0:
                content.ParseFromString(packet.msg.pdata)

                if len(str(content)) > 0:
                    _LOGGER.debug("cmd_id %u: Successfully parsed %s - content length: %d", 
                                packet.msg.cmd_id, content_type, len(str(content)))

                fields_added = 0
                for descriptor in content.DESCRIPTOR.fields:
                    if not content.HasField(descriptor.name):
                        continue

                    value = getattr(content, descriptor.name)
                    raw["params"][descriptor.name] = value
                    fields_added += 1
                
                if fields_added > 0:
                    _LOGGER.debug("cmd_id %u: %s added %d fields", 
                                packet.msg.cmd_id, content_type, fields_added)
                else:
                    _LOGGER.debug("cmd_id %u: %s parsed but no fields found", 
                                packet.msg.cmd_id, content_type)
                    
        except Exception as error:
            # Detailliertes Error-Logging nur für unerwartete Fehler
            if "Failed to parse" not in str(error):
                _LOGGER.debug("cmd_id %u: %s parsing failed: %s", 
                            packet.msg.cmd_id, content_type, str(error))
            # Protobuf-Parse-Fehler sind normal und erwartet für inkompatible Definitionen