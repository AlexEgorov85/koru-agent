import asyncio
from main import Application
import argparse

async def test():
    args = argparse.Namespace()
    args.goal = 'Какие книги написал Пушкин?'
    args.profile = 'dev'
    args.debug = True
    args.max_steps = 1
    args.temperature = 0.3
    args.max_tokens = 512
    args.strategy = 'react'
    args.output = None
    
    app = Application(args)
    try:
        await app.initialize()
        result = await app.run()
        print('SUCCESS: Agent completed')
        print(f'Result: {result}')
    except Exception as e:
        print(f'ERROR: {e}')
        import traceback
        traceback.print_exc()
    finally:
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(test())