"""Exercise the public wire interface via the MCP SDK, without a model account."""
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class StdioContract(unittest.IsolatedAsyncioTestCase):
    async def test_tool_discovery_validation_and_root_isolation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / 'job space'
            env = dict(os.environ)
            env.pop('PYTHONPATH', None)
            params = StdioServerParameters(
                command=sys.executable, cwd=tmp, env=env,
                args=['-m', 'agent_studio.mcp_server', '--output-root', str(root)],
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as client:
                    info = await client.initialize()
                    self.assertEqual(info.serverInfo.name, '3d-agent-studio')
                    tools = await client.list_tools()
                    self.assertEqual({tool.name for tool in tools.tools}, {
                        'studio_doctor', 'studio_brief', 'studio_draft', 'studio_status',
                        'studio_view', 'studio_compare', 'studio_finalize',
                    })
                    result = await client.call_tool('studio_brief', {
                        'brief': {'title': 'Orbit test', 'template': 'orbit-bloom', 'accent': '#00abcd',
                                  'orientation': 'horizontal'},
                    })
                    self.assertFalse(result.isError, result.content)
                    self.assertEqual(result.structuredContent['accent'], '#00ABCD')
                    self.assertEqual(result.structuredContent['seconds'], 6)
                    self.assertEqual(result.structuredContent['orientation'], 'horizontal')
                    invalid = await client.call_tool('studio_draft', {'brief': {'seconds': True}})
                    self.assertTrue(invalid.isError)
                    self.assertIn('seconds', invalid.content[0].text)
                    illegal = await client.call_tool('studio_status', {'job_id': '../outside'})
                    self.assertTrue(illegal.isError)
                    image = await client.call_tool('studio_view', {
                        'job_id': '0' * 32, 'stage': 'preview', 'board': '../../outside.jpg',
                    })
                    self.assertTrue(image.isError)
            self.assertFalse(root.exists())
