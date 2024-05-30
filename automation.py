import asyncio
import time
import json
import aiohttp
import logging
import os

# Configure logging
logging.basicConfig(filename='mailtm_api.log',level=logging.INFO, format="[%(asctime)s %(levelname)s] %(message)s")

MAILTM_BASE_URL = "https://api.mail.tm"
MAX_CONCURRENT_REQUESTS = 25  
EMAIL_ADDRESS = "sh3ffin@fthcapital.com"  
PASSWORD = "test@123"  


        
def write_to_json_file(data, filename="messages.json"):
    """Writes data to a JSON file."""
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {"messages": []}
        else:
            existing_data = {"messages": []}
        
        existing_data["messages"].append(data)
        
        with open(filename, 'w') as f:
            json.dump(existing_data, f, indent=4)
        
        logging.info(f"Successfully wrote data to {filename}")
    except Exception as e:
        logging.error(f"Failed to write to {filename}: {e}")

async def handle_api_error(response):
    if response.status == 429:  # Handle rate limiting error
        logging.warning(f"Rate limit exceeded! Waiting for 5 seconds...")
        await asyncio.sleep(int(5))
        return await handle_api_error(response)  # Retry after waiting
    elif response.status >= 400:
        logging.error(f"API error ({response.status}): {await response.text()}")
        return None
    else:
        logging.info(f"Successful response: {response}")
        return await response.json()  # Return processed data


async def get_jwt_token(session): # Generating jwt token
    async with session.post(f"{MAILTM_BASE_URL}/token", json={"address": EMAIL_ADDRESS, "password": PASSWORD}) as response:
        if response.status == 200:
            response_data = await response.json()
            return response_data.get('token')
        else:
            logging.error(f"Failed to get JWT token ({response.status})")
            return None


async def get_messages(session, token): # Get new messages
    headers = {"Authorization": f"Bearer {token}"}
    async with session.get(f"{MAILTM_BASE_URL}/messages?address={EMAIL_ADDRESS}", headers=headers) as response:
        return await handle_api_error(response)  


async def delete_message(session, token, message_id): # delete a message
    headers = {"Authorization": f"Bearer {token}"}
    async with session.delete(f"{MAILTM_BASE_URL}/messages/{message_id}", headers=headers) as response:
        if response.status == 204:  # Check for success code
            logging.info(f"Message {message_id} deleted successfully")
            return True 
        else:
            return await handle_api_error(response)
        


async def handle_email_operations(session, token):
    response = await get_messages(session, token)
    logging.info(f"Retrieved messages for {EMAIL_ADDRESS}")
    if response: 
        messages = response['hydra:member']
        logging.info(f"Found {len(messages)} messages")
        for message in messages:
            write_to_json_file(message)
            await delete_message(session, token, message['id'])

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

        token = await get_jwt_token(session)
        if not token:
            logging.error("Failed to obtain JWT token")
            return

        for _ in range(MAX_CONCURRENT_REQUESTS):
            tasks.append(asyncio.ensure_future(handle_email_operations(session, token)))

        # Limit the number of concurrent tasks using semaphore
        async with semaphore:
            await asyncio.gather(*tasks)


if __name__ == "__main__":
    start_time = time.time()
    asyncio.run(main())
    print(f"Completed in {time.time() - start_time} seconds")
