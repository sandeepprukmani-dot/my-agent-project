# agent.py
import asyncio
import json
import sys
import os
import base64
import uuid
import socketio
from playwright.async_api import async_playwright

SERVER_URL = os.environ.get('AGENT_SERVER_URL', 'http://127.0.0.1:5000')

sio = socketio.Client(
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1,
    reconnection_delay_max=5,
    logger=False,
    engineio_logger=False
)
agent_id = str(uuid.uuid4())


@sio.event
def connect():
    print(f"Connected to server: {SERVER_URL}")
    available_browsers = ["chromium", "firefox", "webkit"]
    sio.emit('agent_register', {
        'agent_id': agent_id,
        'browsers': available_browsers
    })


@sio.event
def disconnect():
    print("Disconnected from server")


@sio.event
def agent_registered(data):
    print(f"Agent registered successfully: {data}")


@sio.on('execute_on_agent')
def handle_execute(data):
    test_id = data['test_id']
    code = data['code']
    browser = data['browser']
    mode = data['mode']

    print(f"\n{'=' * 50}")
    print(f"Executing test {test_id}")
    print(f"Browser: {browser}, Mode: {mode}")
    print(f"{'=' * 50}\n")

    asyncio.run(execute_test(test_id, code, browser, mode))


async def execute_test(test_id, code, browser_name, mode):
    headless = mode == 'headless'

    try:
        sio.emit('agent_log', {
            'test_id': test_id,
            'message': f'Preparing to execute test in {mode} mode...'
        })

        local_vars = {}
        exec(code, {}, local_vars)

        if 'run_test' not in local_vars:
            sio.emit('agent_result', {
                'test_id': test_id,
                'success': False,
                'logs': ['Error: Generated code must contain a run_test function'],
                'screenshot': None
            })
            return

        run_test = local_vars['run_test']

        sio.emit('agent_log', {
            'test_id': test_id,
            'message': f'Launching {browser_name} browser...'
        })

        result = await run_test(browser_name=browser_name, headless=headless)

        screenshot_b64 = None
        if result.get('screenshot'):
            screenshot_b64 = base64.b64encode(result['screenshot']).decode('utf-8')

        sio.emit('agent_result', {
            'test_id': test_id,
            'success': result.get('success', False),
            'logs': result.get('logs', []),
            'screenshot': screenshot_b64
        })

        print(f"\nTest {test_id} completed: {'SUCCESS' if result.get('success') else 'FAILED'}")

    except Exception as e:
        print(f"Execution error: {e}")
        sio.emit('agent_result', {
            'test_id': test_id,
            'success': False,
            'logs': [f'Agent execution error: {str(e)}'],
            'screenshot': None
        })


def main():
    print(f"Starting Browser Automation Agent")
    print(f"Agent ID: {agent_id}")
    print(f"Server URL: {SERVER_URL}")
    print(f"\nPress Ctrl+C to stop the agent\n")

    while True:
        try:
            print("Connecting to server...")
            sio.connect(
                SERVER_URL,
                transports=['websocket', 'polling'],
                wait_timeout=10
            )
            print("Connection established!")
            sio.wait()
        except KeyboardInterrupt:
            print("\nShutting down agent...")
            sio.disconnect()
            break
        except Exception as e:
            print(f"Error connecting to server: {e}")
            print("Retrying connection in 5 seconds...")
            import time
            time.sleep(5)


if __name__ == '__main__':
    main()
