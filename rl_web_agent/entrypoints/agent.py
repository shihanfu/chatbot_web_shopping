#!/usr/bin/env python3
"""
Agent - Main entry module for running WebAgent tasks
Run with: python -m rl_web_agent.entrypoints.agent
"""

import asyncio
import json
import logging
import os
import shutil
import signal
import sys
import tempfile
from pathlib import Path

from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra

from rl_web_agent.agent import create_web_agent
from rl_web_agent.env import WebAgentEnv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def run_agent_task():
    """Run the WebAgent until task completion (terminated=True)."""
    temp_user_data_dir = None
    temp_cache_dir = None

    try:
        # Create temporary directories for browser data
        temp_user_data_dir = tempfile.mkdtemp(prefix="webagent_userdata_")
        temp_cache_dir = tempfile.mkdtemp(prefix="webagent_cache_")
        logger.info("Created temporary browser directories:")
        logger.info(f"  User data: {temp_user_data_dir}")
        logger.info(f"  Cache: {temp_cache_dir}")

        # Load configuration - use relative path from project root
        config_dir = "../../rl_web_agent/conf"  # Relative path from entrypoints directory
        config_name = "config"

        # Initialize Hydra
        if GlobalHydra().is_initialized():
            GlobalHydra.instance().clear()

        with initialize(version_base=None, config_path=config_dir):
            cfg = compose(config_name=config_name)

        # Override browser directories to use temporary ones
        cfg.environment.browser.user_data_dir = temp_user_data_dir
        cfg.environment.browser.cache_dir = temp_cache_dir

        # Load test task
        project_root = Path(__file__).parent.parent.parent
        test_task_path = project_root / "thirdparty" / "webarena" / "config_files" / "506.json"
        with open(test_task_path) as f:
            test_task = json.load(f)

        # Create environment and agent
        env = WebAgentEnv(cfg.environment)
        agent = await create_web_agent(cfg.llm)

        try:
            # Setup environment with test task
            await env.setup(test_task)
            logger.info(f"Environment setup complete for task: {test_task['intent']}")

            # Run the task until completion (terminated=True)
            logger.info("Starting agent task execution - will run until terminated")
            result = await agent.run_task(env, test_task["intent"], max_steps=50)

            # Print final results
            logger.info("=" * 60)
            logger.info("TASK COMPLETION SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Success: {result['success']}")
            logger.info(f"Score: {result['score']}")
            logger.info(f"Answer: {result['answer']}")
            logger.info(f"Steps: {result['steps']}")
            logger.info(f"Terminated: {result['terminated']}")
            logger.info(f"Max steps reached: {result['max_steps_reached']}")
            logger.info("=" * 60)

            if result["terminated"]:
                if result["success"]:
                    logger.info("✅ Task completed successfully!")
                else:
                    logger.info("❌ Task terminated but failed")
            else:
                logger.info("⚠️  Task stopped without termination (max steps reached)")

        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            raise
        finally:
            # Cleanup environment
            await env.close()
            logger.info("Environment closed")

    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        raise
    finally:
        # Clean up temporary directories
        if temp_user_data_dir and os.path.exists(temp_user_data_dir):
            try:
                shutil.rmtree(temp_user_data_dir)
                logger.info(f"Cleaned up temporary user data directory: {temp_user_data_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up user data directory: {e}")

        if temp_cache_dir and os.path.exists(temp_cache_dir):
            try:
                shutil.rmtree(temp_cache_dir)
                logger.info(f"Cleaned up temporary cache directory: {temp_cache_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up cache directory: {e}")


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully"""
    logger.info(f"Received signal {signum}. Cleaning up...")
    sys.exit(0)


def main():
    """Main entry point"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        asyncio.run(run_agent_task())
    except KeyboardInterrupt:
        logger.info("Agent interrupted by user")
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
