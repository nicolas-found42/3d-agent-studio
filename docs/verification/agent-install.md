# Verify an agent install

Confirm that your agent can use the local render machine and inspect the result. Start in a fresh session after following the [guide for your host](../marketplace.md).

1. Call `studio_doctor` in a fresh session. Check the job root and the Blender, FFmpeg and FFprobe versions.
2. Call `studio_examples` with `query: "product"` and `include_script: true`. Check that you get a scene script and local poster and clip paths.
3. Call `studio_draft` with `brief: {"prompt":"A red cube turns on a grey floor","orientation":"square","seconds":2}` and this Python as `script`.

   ```python
   def build(kit):
       kit.ground()
       cube = kit.box("Cube", 1, (0, 0, .5), kit.material("Red", "#BD3026"))
       kit.spin(cube)
       kit.sun()
       kit.camera()
   ```

4. Poll `studio_status` until `preview.state` is `ready`. Use `studio_view` for `timeline.jpg` and `angles.jpg`. If the host does not show MCP images inline, open the local paths. The six images in the timeline should show the cube turning.
