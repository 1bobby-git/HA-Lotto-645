"""Binary entities: prize outcome detail and the Lotto Lab service health check."""
from __future__ import annotations
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory
from .entity import Lotto645Entity
from .result_details import winning_attributes

PARALLEL_UPDATES = 0

CONNECTION_TYPES = {
    'member': '회원 계정 연결',
    'automatic': '자동 연결 (계정 미연결)',
    'operator': '운영자 연결',
}


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LottoWinningDetailSensor(entry.runtime_data),
                        LottoServiceConnectionSensor(entry.runtime_data)])


class LottoWinningDetailSensor(Lotto645Entity, BinarySensorEntity):
    _lotto_group = 'results'
    _attr_has_entity_name = False
    _attr_icon = 'mdi:ticket-confirmation-outline'
    _unrecorded_attributes = frozenset({'results', 'winners', 'losers'})

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f'{coordinator.entry.entry_id}_winning_detail'

    @property
    def name(self):
        round_no = self.coordinator.result_round
        return f'{round_no}회 당첨 상세' if round_no else '당첨 상세'

    @property
    def available(self):
        return self.coordinator.data is not None

    @property
    def is_on(self):
        report = self.coordinator.winning_summary
        if (not report or report.get('status') != 'evaluated'
                or not report.get('checked_game_count')):
            return None  # unavailable/unknown is NOT a losing ticket
        return report['winning_game_count'] > 0

    @property
    def extra_state_attributes(self):
        return winning_attributes(self.coordinator)


class LottoServiceConnectionSensor(Lotto645Entity, BinarySensorEntity):
    """On while the last authenticated health check of the number service succeeded."""

    _attr_name = 'Lotto Lab 연결'
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f'{coordinator.entry.entry_id}_service_connection'

    @property
    def available(self):
        return True  # the connection state itself is the reported value

    @property
    def is_on(self):
        return self.coordinator.service.health.get('ok')

    @property
    def extra_state_attributes(self):
        service = self.coordinator.service
        health = service.health
        source = (service.connection_manager.state or {}).get('source')
        return {
            'connection_type': CONNECTION_TYPES.get(source, '연결 정보 없음'),
            'account_linked': source == 'member',
            'member_link': (service.member_link or {}).get('status'),
            'service_status': service.status,
            'last_error': health.get('error'),
            'status_since': health.get('since'),
            'device_id': service.info.get('device_id'),
            'core_version': health.get('core_version'),
            'latest_round': health.get('latest_round'),
            'health_check': '5분마다 Lotto Lab 서비스에 이 기기의 인증 정보로 상태 확인 요청을 보냅니다.',
        }
