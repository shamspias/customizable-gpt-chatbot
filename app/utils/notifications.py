import aiohttp
import logging


class NotificationSender:
    def __init__(self, base_url):
        self.base_url = base_url

    async def send_notification(self, conversation_id, data):
        url = f"{self.base_url}/{conversation_id}/messages"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    if result.get("success"):
                        return True
                    else:
                        logging.error(f"Failed to send notification: {result}")
                        return False
            except Exception as e:
                logging.error(f"Error sending notification: {e}")
                return False
