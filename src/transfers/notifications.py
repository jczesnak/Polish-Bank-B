from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def send_user_event(user_id, event_type, payload):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f'user_{user_id}',
        {
            'type': 'bank.event',
            'event': event_type,
            'payload': payload,
        },
    )
