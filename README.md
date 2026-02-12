# zoneminder-prometheus-exporter

A docker-based Prometheus exporter for ZoneMinder.

[![Project Status: WIP – Initial development is in progress, but there has not yet been a stable, usable release suitable for the public.](https://www.repostatus.org/badges/latest/wip.svg)](https://www.repostatus.org/#wip)

**IMPORTANT:** This is a personal project only. PRs are accepted, but this is not supported and "issues" will likely not be fixed or responded to. This is only for people who understand the details of everything invovled.

## Usage

This is really only intended to be run in Docker; if you need to run it locally, make your environment like the Docker container.

If you are also running ZoneMinder itself inside Docker, i.e. with [my docker-zoneminder image](https://github.com/jantman/docker-zoneminder), then you will need to run zoneminder with ``--ipc="shareable"`` and this container with ``--ipc="container:name-of-zm-container"``; this is to allow the collector in this container to read from ZM's shared memory. If you are running ZoneMinder directly on the host, run this container with ``--ipc="host"`` (which is probably a security risk). This container **must run on the same machine as zoneminder** in order to access shared memory. 

```
docker run -p 8080:8080 \
    -e ZM_API_URL=http://zm/api \
    -e ZMES_WEBSOCKET_URL=ws://zm:9000 \
    -e ZM_USER=myuser \
    -e ZM_PASSWORD=mypassword \
    --ipc="container:zm" \
    jantman/zoneminder-prometheus-exporter:latest
```

Note: `ZM_USER` and `ZM_PASSWORD` are only needed if your ZoneMinder instance has authentication enabled (`OPT_USE_AUTH`).

### Known Issues and Limitations

* I'm using the [pyzm](https://github.com/ZoneMinder/pyzm) package since it's already written. It is emphatically non-Pythonic, so if you attempt to use the [main.py](main.py) python module on its own or do any development work, be aware of that. This is up to and including ignoring Python's built-in `logging` library and implementing its own non-compatible logging layer. There's also a lot of incorrect documentation, especially about types. Be warned.

### Environment Variables

* `ZM_API_URL` (**required**) - ZoneMinder API URL, e.g. `http://zmhost/zm/api`
* `ZM_USER` (*optional*) - ZoneMinder username for authentication. Required if ZoneMinder has `OPT_USE_AUTH` enabled. Must be provided together with `ZM_PASSWORD`.
* `ZM_PASSWORD` (*optional*) - ZoneMinder password for authentication. Required if ZoneMinder has `OPT_USE_AUTH` enabled. Must be provided together with `ZM_USER`.
* `ZMES_WEBSOCKET_URL` (*optional*) - ZMES Websocket URL, if you also want to test connectivity to that

## Grafana Dashboard

A Grafana dashboard for the most important metrics can be found in [grafana-dashboard.json](grafana-dashboard.json).

## Debugging

For debugging, append `-vv` to your `docker run` command, to run the entrypoint with debug-level logging.

## Metrics Exposed and Example Output

```
# HELP zm_monitor_info_info Information about a monitor
# TYPE zm_monitor_info_info gauge
zm_monitor_info_info{channel="0",control_id="41",controllable="0",decoding_enabled="1",device="",encoder="libx264",event_prefix="FrontPorch-",format="0",importance="Normal",method="rtpRtsp",record_audio="1",server_id="0",storage_id="0",type="Ffmpeg"} 1.0
zm_monitor_info_info{channel="0",control_id="41",controllable="1",decoding_enabled="1",device="",encoder="libx264",event_prefix="Office-",format="0",importance="Normal",method="rtpRtsp",record_audio="1",server_id="0",storage_id="0",type="Ffmpeg"} 1.0
zm_monitor_info_info{channel="0",control_id="41",controllable="1",decoding_enabled="1",device="",encoder="libx264",event_prefix="DiningRoom-",format="0",importance="Normal",method="rtpRtsp",record_audio="1",server_id="0",storage_id="0",type="Ffmpeg"} 1.0
zm_monitor_info_info{channel="0",control_id="41",controllable="1",decoding_enabled="1",device="",encoder="libx264",event_prefix="LivingRoom-",format="0",importance="Normal",method="rtpRtsp",record_audio="1",server_id="0",storage_id="0",type="Ffmpeg"} 1.0
zm_monitor_info_info{channel="0",control_id="41",controllable="0",decoding_enabled="1",device="",encoder="libx264",event_prefix="BsmtDoorRm-",format="0",importance="Normal",method="rtpRtsp",record_audio="1",server_id="0",storage_id="0",type="Ffmpeg"} 1.0
zm_monitor_info_info{channel="0",control_id="41",controllable="1",decoding_enabled="1",device="",encoder="libx264",event_prefix="Cats-",format="0",importance="Normal",method="rtpRtsp",record_audio="1",server_id="0",storage_id="0",type="Ffmpeg"} 1.0
# HELP zm_monitor_event_count Monitor event count
# TYPE zm_monitor_event_count gauge
zm_monitor_event_count{id="1",name="FrontPorch"} 304.0
zm_monitor_event_count{id="2",name="Office"} 145.0
zm_monitor_event_count{id="3",name="DiningRoom"} 287.0
zm_monitor_event_count{id="4",name="LivingRoom"} 38.0
zm_monitor_event_count{id="5",name="BasementDoorRm"} 159.0
zm_monitor_event_count{id="6",name="Cats"} 281.0
# HELP zm_monitor_enabled Monitor is enabled
# TYPE zm_monitor_enabled gauge
zm_monitor_enabled{id="1",name="FrontPorch"} 1.0
zm_monitor_enabled{id="2",name="Office"} 1.0
zm_monitor_enabled{id="3",name="DiningRoom"} 1.0
zm_monitor_enabled{id="4",name="LivingRoom"} 1.0
zm_monitor_enabled{id="5",name="BasementDoorRm"} 1.0
zm_monitor_enabled{id="6",name="Cats"} 1.0
# HELP zm_monitor_function Monitor function
# TYPE zm_monitor_function gauge
zm_monitor_function{id="1",name="FrontPorch",zm_monitor_function="Mocord"} 0.0
zm_monitor_function{id="1",name="FrontPorch",zm_monitor_function="Modect"} 1.0
zm_monitor_function{id="1",name="FrontPorch",zm_monitor_function="Monitor"} 0.0
zm_monitor_function{id="1",name="FrontPorch",zm_monitor_function="Nodect"} 0.0
zm_monitor_function{id="1",name="FrontPorch",zm_monitor_function="None"} 0.0
zm_monitor_function{id="1",name="FrontPorch",zm_monitor_function="Record"} 0.0
zm_monitor_function{id="2",name="Office",zm_monitor_function="Mocord"} 0.0
zm_monitor_function{id="2",name="Office",zm_monitor_function="Modect"} 0.0
zm_monitor_function{id="2",name="Office",zm_monitor_function="Monitor"} 0.0
zm_monitor_function{id="2",name="Office",zm_monitor_function="Nodect"} 0.0
zm_monitor_function{id="2",name="Office",zm_monitor_function="None"} 1.0
zm_monitor_function{id="2",name="Office",zm_monitor_function="Record"} 0.0
zm_monitor_function{id="3",name="DiningRoom",zm_monitor_function="Mocord"} 0.0
zm_monitor_function{id="3",name="DiningRoom",zm_monitor_function="Modect"} 0.0
zm_monitor_function{id="3",name="DiningRoom",zm_monitor_function="Monitor"} 1.0
zm_monitor_function{id="3",name="DiningRoom",zm_monitor_function="Nodect"} 0.0
zm_monitor_function{id="3",name="DiningRoom",zm_monitor_function="None"} 0.0
zm_monitor_function{id="3",name="DiningRoom",zm_monitor_function="Record"} 0.0
zm_monitor_function{id="4",name="LivingRoom",zm_monitor_function="Mocord"} 0.0
zm_monitor_function{id="4",name="LivingRoom",zm_monitor_function="Modect"} 0.0
zm_monitor_function{id="4",name="LivingRoom",zm_monitor_function="Monitor"} 1.0
zm_monitor_function{id="4",name="LivingRoom",zm_monitor_function="Nodect"} 0.0
zm_monitor_function{id="4",name="LivingRoom",zm_monitor_function="None"} 0.0
zm_monitor_function{id="4",name="LivingRoom",zm_monitor_function="Record"} 0.0
zm_monitor_function{id="5",name="BasementDoorRm",zm_monitor_function="Mocord"} 0.0
zm_monitor_function{id="5",name="BasementDoorRm",zm_monitor_function="Modect"} 0.0
zm_monitor_function{id="5",name="BasementDoorRm",zm_monitor_function="Monitor"} 1.0
zm_monitor_function{id="5",name="BasementDoorRm",zm_monitor_function="Nodect"} 0.0
zm_monitor_function{id="5",name="BasementDoorRm",zm_monitor_function="None"} 0.0
zm_monitor_function{id="5",name="BasementDoorRm",zm_monitor_function="Record"} 0.0
zm_monitor_function{id="6",name="Cats",zm_monitor_function="Mocord"} 0.0
zm_monitor_function{id="6",name="Cats",zm_monitor_function="Modect"} 1.0
zm_monitor_function{id="6",name="Cats",zm_monitor_function="Monitor"} 0.0
zm_monitor_function{id="6",name="Cats",zm_monitor_function="Nodect"} 0.0
zm_monitor_function{id="6",name="Cats",zm_monitor_function="None"} 0.0
zm_monitor_function{id="6",name="Cats",zm_monitor_function="Record"} 0.0
# HELP zm_monitor_connected Monitor is connected or not
# TYPE zm_monitor_connected gauge
zm_monitor_connected{id="1",name="FrontPorch",status="Connected"} 1.0
zm_monitor_connected{id="2",name="Office",status="NotRunning"} 0.0
zm_monitor_connected{id="3",name="DiningRoom",status="Connected"} 1.0
zm_monitor_connected{id="4",name="LivingRoom",status="Connected"} 1.0
zm_monitor_connected{id="5",name="BasementDoorRm",status="Connected"} 1.0
zm_monitor_connected{id="6",name="Cats",status="Connected"} 1.0
# HELP zm_monitor_capture_fps Monitor capture FPS
# TYPE zm_monitor_capture_fps gauge
zm_monitor_capture_fps{id="1",name="FrontPorch"} 10.01
zm_monitor_capture_fps{id="2",name="Office"} 10.0
zm_monitor_capture_fps{id="3",name="DiningRoom"} 10.0
zm_monitor_capture_fps{id="4",name="LivingRoom"} 10.0
zm_monitor_capture_fps{id="5",name="BasementDoorRm"} 25.05
zm_monitor_capture_fps{id="6",name="Cats"} 10.0
# HELP zm_monitor_analysis_fps Monitor analysis FPS
# TYPE zm_monitor_analysis_fps gauge
zm_monitor_analysis_fps{id="1",name="FrontPorch"} 10.01
zm_monitor_analysis_fps{id="2",name="Office"} 0.0
zm_monitor_analysis_fps{id="3",name="DiningRoom"} 0.0
zm_monitor_analysis_fps{id="4",name="LivingRoom"} 0.0
zm_monitor_analysis_fps{id="5",name="BasementDoorRm"} 0.0
zm_monitor_analysis_fps{id="6",name="Cats"} 10.0
# HELP zm_monitor_capture_bandwidth_bytes_per_second Monitor capture bandwidth
# TYPE zm_monitor_capture_bandwidth_bytes_per_second gauge
zm_monitor_capture_bandwidth_bytes_per_second{id="1",name="FrontPorch"} 134241.0
zm_monitor_capture_bandwidth_bytes_per_second{id="2",name="Office"} 132993.0
zm_monitor_capture_bandwidth_bytes_per_second{id="3",name="DiningRoom"} 90941.0
zm_monitor_capture_bandwidth_bytes_per_second{id="4",name="LivingRoom"} 117344.0
zm_monitor_capture_bandwidth_bytes_per_second{id="5",name="BasementDoorRm"} 44970.0
zm_monitor_capture_bandwidth_bytes_per_second{id="6",name="Cats"} 507713.0
# HELP zm_monitor_event_disk_space_bytes Monitor event disk space
# TYPE zm_monitor_event_disk_space_bytes gauge
zm_monitor_event_disk_space_bytes{id="1",name="FrontPorch"} 2.342862049e+010
zm_monitor_event_disk_space_bytes{id="2",name="Office"} 5.493280521e+09
zm_monitor_event_disk_space_bytes{id="3",name="DiningRoom"} 6.533904769e+09
zm_monitor_event_disk_space_bytes{id="4",name="LivingRoom"} 1.614962868e+09
zm_monitor_event_disk_space_bytes{id="5",name="BasementDoorRm"} 1.3239581437e+010
zm_monitor_event_disk_space_bytes{id="6",name="Cats"} 4.548615971e+09
# HELP zm_monitor_archived_event_count Monitor archived event count
# TYPE zm_monitor_archived_event_count gauge
zm_monitor_archived_event_count{id="1",name="FrontPorch"} 8.0
zm_monitor_archived_event_count{id="2",name="Office"} 0.0
zm_monitor_archived_event_count{id="3",name="DiningRoom"} 0.0
zm_monitor_archived_event_count{id="4",name="LivingRoom"} 0.0
zm_monitor_archived_event_count{id="5",name="BasementDoorRm"} 0.0
zm_monitor_archived_event_count{id="6",name="Cats"} 0.0
# HELP zm_monitor_archived_event_disk_space_bytes Monitor archived event disk space
# TYPE zm_monitor_archived_event_disk_space_bytes gauge
zm_monitor_archived_event_disk_space_bytes{id="1",name="FrontPorch"} 4.91845528e+08
zm_monitor_archived_event_disk_space_bytes{id="2",name="Office"} 0.0
zm_monitor_archived_event_disk_space_bytes{id="3",name="DiningRoom"} 0.0
zm_monitor_archived_event_disk_space_bytes{id="4",name="LivingRoom"} 0.0
zm_monitor_archived_event_disk_space_bytes{id="5",name="BasementDoorRm"} 0.0
zm_monitor_archived_event_disk_space_bytes{id="6",name="Cats"} 0.0
# HELP zm_monitor_zmc_uptime_seconds Uptime of monitor zmc process in seconds
# TYPE zm_monitor_zmc_uptime_seconds gauge
zm_monitor_zmc_uptime_seconds{command="zmc -m 1",id="1",name="FrontPorch"} 93549.676232
zm_monitor_zmc_uptime_seconds{command="zmc -m 3",id="3",name="DiningRoom"} 93548.955353
zm_monitor_zmc_uptime_seconds{command="zmc -m 4",id="4",name="LivingRoom"} 93549.206867
zm_monitor_zmc_uptime_seconds{command="zmc -m 5",id="5",name="BasementDoorRm"} 93548.396913
zm_monitor_zmc_uptime_seconds{command="zmc -m 6",id="6",name="Cats"} 32493.632874
# HELP zm_monitor_zmc_pid Monitor zmc process PID
# TYPE zm_monitor_zmc_pid gauge
zm_monitor_zmc_pid{command="zmc -m 1",id="1",name="FrontPorch"} 75.0
zm_monitor_zmc_pid{command="zmc -m 3",id="3",name="DiningRoom"} 86.0
zm_monitor_zmc_pid{command="zmc -m 4",id="4",name="LivingRoom"} 95.0
zm_monitor_zmc_pid{command="zmc -m 5",id="5",name="BasementDoorRm"} 103.0
zm_monitor_zmc_pid{command="zmc -m 6",id="6",name="Cats"} 125926.0
# HELP zm_monitor_decoding_enabled ZM Monitor DecodingEnabled
# TYPE zm_monitor_decoding_enabled gauge
zm_monitor_decoding_enabled{id="1",name="FrontPorch"} 1.0
zm_monitor_decoding_enabled{id="2",name="Office"} 1.0
zm_monitor_decoding_enabled{id="3",name="DiningRoom"} 1.0
zm_monitor_decoding_enabled{id="4",name="LivingRoom"} 1.0
zm_monitor_decoding_enabled{id="5",name="BasementDoorRm"} 1.0
zm_monitor_decoding_enabled{id="6",name="Cats"} 1.0
# HELP zm_monitor_width ZM Monitor Width
# TYPE zm_monitor_width gauge
zm_monitor_width{id="1",name="FrontPorch"} 1920.0
zm_monitor_width{id="2",name="Office"} 1920.0
zm_monitor_width{id="3",name="DiningRoom"} 1920.0
zm_monitor_width{id="4",name="LivingRoom"} 1920.0
zm_monitor_width{id="5",name="BasementDoorRm"} 1920.0
zm_monitor_width{id="6",name="Cats"} 1920.0
# HELP zm_monitor_height ZM Monitor Height
# TYPE zm_monitor_height gauge
zm_monitor_height{id="1",name="FrontPorch"} 1080.0
zm_monitor_height{id="2",name="Office"} 1080.0
zm_monitor_height{id="3",name="DiningRoom"} 1080.0
zm_monitor_height{id="4",name="LivingRoom"} 1080.0
zm_monitor_height{id="5",name="BasementDoorRm"} 1080.0
zm_monitor_height{id="6",name="Cats"} 1080.0
# HELP zm_monitor_colours ZM Monitor Colours
# TYPE zm_monitor_colours gauge
zm_monitor_colours{id="1",name="FrontPorch"} 4.0
zm_monitor_colours{id="2",name="Office"} 4.0
zm_monitor_colours{id="3",name="DiningRoom"} 4.0
zm_monitor_colours{id="4",name="LivingRoom"} 4.0
zm_monitor_colours{id="5",name="BasementDoorRm"} 4.0
zm_monitor_colours{id="6",name="Cats"} 4.0
# HELP zm_monitor_palette ZM Monitor Palette
# TYPE zm_monitor_palette gauge
zm_monitor_palette{id="1",name="FrontPorch"} 0.0
zm_monitor_palette{id="2",name="Office"} 0.0
zm_monitor_palette{id="3",name="DiningRoom"} 0.0
zm_monitor_palette{id="4",name="LivingRoom"} 0.0
zm_monitor_palette{id="5",name="BasementDoorRm"} 0.0
zm_monitor_palette{id="6",name="Cats"} 0.0
# HELP zm_monitor_save_jpegs ZM Monitor SaveJPEGs
# TYPE zm_monitor_save_jpegs gauge
zm_monitor_save_jpegs{id="1",name="FrontPorch"} 3.0
zm_monitor_save_jpegs{id="2",name="Office"} 3.0
zm_monitor_save_jpegs{id="3",name="DiningRoom"} 3.0
zm_monitor_save_jpegs{id="4",name="LivingRoom"} 3.0
zm_monitor_save_jpegs{id="5",name="BasementDoorRm"} 3.0
zm_monitor_save_jpegs{id="6",name="Cats"} 3.0
# HELP zm_monitor_video_writer ZM Monitor VideoWriter
# TYPE zm_monitor_video_writer gauge
zm_monitor_video_writer{id="1",name="FrontPorch"} 1.0
zm_monitor_video_writer{id="2",name="Office"} 1.0
zm_monitor_video_writer{id="3",name="DiningRoom"} 1.0
zm_monitor_video_writer{id="4",name="LivingRoom"} 1.0
zm_monitor_video_writer{id="5",name="BasementDoorRm"} 1.0
zm_monitor_video_writer{id="6",name="Cats"} 1.0
# HELP zm_monitor_output_codec ZM Monitor OutputCodec
# TYPE zm_monitor_output_codec gauge
zm_monitor_output_codec{id="1",name="FrontPorch"} 27.0
zm_monitor_output_codec{id="2",name="Office"} 27.0
zm_monitor_output_codec{id="3",name="DiningRoom"} 27.0
zm_monitor_output_codec{id="4",name="LivingRoom"} 27.0
zm_monitor_output_codec{id="5",name="BasementDoorRm"} 27.0
zm_monitor_output_codec{id="6",name="Cats"} 27.0
# HELP zm_monitor_brightness ZM Monitor Brightness
# TYPE zm_monitor_brightness gauge
zm_monitor_brightness{id="1",name="FrontPorch"} -1.0
zm_monitor_brightness{id="2",name="Office"} -1.0
zm_monitor_brightness{id="3",name="DiningRoom"} -1.0
zm_monitor_brightness{id="4",name="LivingRoom"} -1.0
zm_monitor_brightness{id="5",name="BasementDoorRm"} -1.0
zm_monitor_brightness{id="6",name="Cats"} -1.0
# HELP zm_monitor_contrast ZM Monitor Contrast
# TYPE zm_monitor_contrast gauge
zm_monitor_contrast{id="1",name="FrontPorch"} -1.0
zm_monitor_contrast{id="2",name="Office"} -1.0
zm_monitor_contrast{id="3",name="DiningRoom"} -1.0
zm_monitor_contrast{id="4",name="LivingRoom"} -1.0
zm_monitor_contrast{id="5",name="BasementDoorRm"} -1.0
zm_monitor_contrast{id="6",name="Cats"} -1.0
# HELP zm_monitor_hue ZM Monitor Hue
# TYPE zm_monitor_hue gauge
zm_monitor_hue{id="1",name="FrontPorch"} -1.0
zm_monitor_hue{id="2",name="Office"} -1.0
zm_monitor_hue{id="3",name="DiningRoom"} -1.0
zm_monitor_hue{id="4",name="LivingRoom"} -1.0
zm_monitor_hue{id="5",name="BasementDoorRm"} -1.0
zm_monitor_hue{id="6",name="Cats"} -1.0
# HELP zm_monitor_colour ZM Monitor Colour
# TYPE zm_monitor_colour gauge
zm_monitor_colour{id="1",name="FrontPorch"} -1.0
zm_monitor_colour{id="2",name="Office"} -1.0
zm_monitor_colour{id="3",name="DiningRoom"} -1.0
zm_monitor_colour{id="4",name="LivingRoom"} -1.0
zm_monitor_colour{id="5",name="BasementDoorRm"} -1.0
zm_monitor_colour{id="6",name="Cats"} -1.0
# HELP zm_monitor_image_buffer_count ZM Monitor ImageBufferCount
# TYPE zm_monitor_image_buffer_count gauge
zm_monitor_image_buffer_count{id="1",name="FrontPorch"} 5.0
zm_monitor_image_buffer_count{id="2",name="Office"} 5.0
zm_monitor_image_buffer_count{id="3",name="DiningRoom"} 5.0
zm_monitor_image_buffer_count{id="4",name="LivingRoom"} 5.0
zm_monitor_image_buffer_count{id="5",name="BasementDoorRm"} 5.0
zm_monitor_image_buffer_count{id="6",name="Cats"} 5.0
# HELP zm_monitor_max_image_buffer_count ZM Monitor MaxImageBufferCount
# TYPE zm_monitor_max_image_buffer_count gauge
zm_monitor_max_image_buffer_count{id="1",name="FrontPorch"} 0.0
zm_monitor_max_image_buffer_count{id="2",name="Office"} 0.0
zm_monitor_max_image_buffer_count{id="3",name="DiningRoom"} 0.0
zm_monitor_max_image_buffer_count{id="4",name="LivingRoom"} 0.0
zm_monitor_max_image_buffer_count{id="5",name="BasementDoorRm"} 0.0
zm_monitor_max_image_buffer_count{id="6",name="Cats"} 0.0
# HELP zm_monitor_warmup_count ZM Monitor WarmupCount
# TYPE zm_monitor_warmup_count gauge
zm_monitor_warmup_count{id="1",name="FrontPorch"} 0.0
zm_monitor_warmup_count{id="2",name="Office"} 0.0
zm_monitor_warmup_count{id="3",name="DiningRoom"} 0.0
zm_monitor_warmup_count{id="4",name="LivingRoom"} 0.0
zm_monitor_warmup_count{id="5",name="BasementDoorRm"} 0.0
zm_monitor_warmup_count{id="6",name="Cats"} 0.0
# HELP zm_monitor_pre_event_count ZM Monitor PreEventCount
# TYPE zm_monitor_pre_event_count gauge
zm_monitor_pre_event_count{id="1",name="FrontPorch"} 5.0
zm_monitor_pre_event_count{id="2",name="Office"} 5.0
zm_monitor_pre_event_count{id="3",name="DiningRoom"} 5.0
zm_monitor_pre_event_count{id="4",name="LivingRoom"} 5.0
zm_monitor_pre_event_count{id="5",name="BasementDoorRm"} 5.0
zm_monitor_pre_event_count{id="6",name="Cats"} 5.0
# HELP zm_monitor_post_event_count ZM Monitor PostEventCount
# TYPE zm_monitor_post_event_count gauge
zm_monitor_post_event_count{id="1",name="FrontPorch"} 5.0
zm_monitor_post_event_count{id="2",name="Office"} 5.0
zm_monitor_post_event_count{id="3",name="DiningRoom"} 5.0
zm_monitor_post_event_count{id="4",name="LivingRoom"} 5.0
zm_monitor_post_event_count{id="5",name="BasementDoorRm"} 5.0
zm_monitor_post_event_count{id="6",name="Cats"} 5.0
# HELP zm_monitor_alarm_frame_count ZM Monitor AlarmFrameCount
# TYPE zm_monitor_alarm_frame_count gauge
zm_monitor_alarm_frame_count{id="1",name="FrontPorch"} 1.0
zm_monitor_alarm_frame_count{id="2",name="Office"} 1.0
zm_monitor_alarm_frame_count{id="3",name="DiningRoom"} 1.0
zm_monitor_alarm_frame_count{id="4",name="LivingRoom"} 1.0
zm_monitor_alarm_frame_count{id="5",name="BasementDoorRm"} 1.0
zm_monitor_alarm_frame_count{id="6",name="Cats"} 1.0
# HELP zm_monitor_ref_blend_perc ZM Monitor RefBlendPerc
# TYPE zm_monitor_ref_blend_perc gauge
zm_monitor_ref_blend_perc{id="1",name="FrontPorch"} 12.0
zm_monitor_ref_blend_perc{id="2",name="Office"} 6.0
zm_monitor_ref_blend_perc{id="3",name="DiningRoom"} 6.0
zm_monitor_ref_blend_perc{id="4",name="LivingRoom"} 6.0
zm_monitor_ref_blend_perc{id="5",name="BasementDoorRm"} 6.0
zm_monitor_ref_blend_perc{id="6",name="Cats"} 6.0
# HELP zm_monitor_alarm_ref_blend_perc ZM Monitor AlarmRefBlendPerc
# TYPE zm_monitor_alarm_ref_blend_perc gauge
zm_monitor_alarm_ref_blend_perc{id="1",name="FrontPorch"} 6.0
zm_monitor_alarm_ref_blend_perc{id="2",name="Office"} 6.0
zm_monitor_alarm_ref_blend_perc{id="3",name="DiningRoom"} 6.0
zm_monitor_alarm_ref_blend_perc{id="4",name="LivingRoom"} 6.0
zm_monitor_alarm_ref_blend_perc{id="5",name="BasementDoorRm"} 6.0
zm_monitor_alarm_ref_blend_perc{id="6",name="Cats"} 6.0
# HELP zm_monitor_track_motion ZM Monitor TrackMotion
# TYPE zm_monitor_track_motion gauge
zm_monitor_track_motion{id="1",name="FrontPorch"} 0.0
zm_monitor_track_motion{id="2",name="Office"} 0.0
zm_monitor_track_motion{id="3",name="DiningRoom"} 0.0
zm_monitor_track_motion{id="4",name="LivingRoom"} 0.0
zm_monitor_track_motion{id="5",name="BasementDoorRm"} 0.0
zm_monitor_track_motion{id="6",name="Cats"} 0.0
# HELP zm_monitor_zone_count ZM Monitor ZoneCount
# TYPE zm_monitor_zone_count gauge
zm_monitor_zone_count{id="1",name="FrontPorch"} 1.0
zm_monitor_zone_count{id="2",name="Office"} 1.0
zm_monitor_zone_count{id="3",name="DiningRoom"} 1.0
zm_monitor_zone_count{id="4",name="LivingRoom"} 1.0
zm_monitor_zone_count{id="5",name="BasementDoorRm"} 1.0
zm_monitor_zone_count{id="6",name="Cats"} 1.0
# HELP zm_state Monitor state
# TYPE zm_state gauge
zm_state{definition="None",id="1",name="default"} 1.0
# HELP zm_monitor_mmap_action ZM Monitor MMAP field action
# TYPE zm_monitor_mmap_action gauge
zm_monitor_mmap_action{id="1",name="FrontPorch"} 0.0
zm_monitor_mmap_action{id="3",name="DiningRoom"} 0.0
zm_monitor_mmap_action{id="4",name="LivingRoom"} 0.0
zm_monitor_mmap_action{id="5",name="BasementDoorRm"} 0.0
zm_monitor_mmap_action{id="6",name="Cats"} 0.0
# HELP zm_monitor_mmap_audio_channels ZM Monitor MMAP field audio_channels
# TYPE zm_monitor_mmap_audio_channels gauge
zm_monitor_mmap_audio_channels{id="1",name="FrontPorch"} 1.0
zm_monitor_mmap_audio_channels{id="3",name="DiningRoom"} 1.0
zm_monitor_mmap_audio_channels{id="4",name="LivingRoom"} 1.0
zm_monitor_mmap_audio_channels{id="5",name="BasementDoorRm"} 1.0
zm_monitor_mmap_audio_channels{id="6",name="Cats"} 1.0
# HELP zm_monitor_mmap_audio_frequency ZM Monitor MMAP field audio_frequency
# TYPE zm_monitor_mmap_audio_frequency gauge
zm_monitor_mmap_audio_frequency{id="1",name="FrontPorch"} 8000.0
zm_monitor_mmap_audio_frequency{id="3",name="DiningRoom"} 16000.0
zm_monitor_mmap_audio_frequency{id="4",name="LivingRoom"} 16000.0
zm_monitor_mmap_audio_frequency{id="5",name="BasementDoorRm"} 16000.0
zm_monitor_mmap_audio_frequency{id="6",name="Cats"} 16000.0
# HELP zm_monitor_mmap_imagesize ZM Monitor MMAP field imagesize
# TYPE zm_monitor_mmap_imagesize gauge
zm_monitor_mmap_imagesize{id="1",name="FrontPorch"} 8.2944e+06
zm_monitor_mmap_imagesize{id="3",name="DiningRoom"} 8.2944e+06
zm_monitor_mmap_imagesize{id="4",name="LivingRoom"} 8.2944e+06
zm_monitor_mmap_imagesize{id="5",name="BasementDoorRm"} 8.2944e+06
zm_monitor_mmap_imagesize{id="6",name="Cats"} 8.2944e+06
# HELP zm_monitor_mmap_last_event ZM Monitor MMAP field last_event
# TYPE zm_monitor_mmap_last_event gauge
zm_monitor_mmap_last_event{id="1",name="FrontPorch"} 1214.0
zm_monitor_mmap_last_event{id="3",name="DiningRoom"} 0.0
zm_monitor_mmap_last_event{id="4",name="LivingRoom"} 0.0
zm_monitor_mmap_last_event{id="5",name="BasementDoorRm"} 0.0
zm_monitor_mmap_last_event{id="6",name="Cats"} 1206.0
# HELP zm_monitor_mmap_last_frame_score ZM Monitor MMAP field last_frame_score
# TYPE zm_monitor_mmap_last_frame_score gauge
zm_monitor_mmap_last_frame_score{id="1",name="FrontPorch"} 0.0
zm_monitor_mmap_last_frame_score{id="3",name="DiningRoom"} 0.0
zm_monitor_mmap_last_frame_score{id="4",name="LivingRoom"} 0.0
zm_monitor_mmap_last_frame_score{id="5",name="BasementDoorRm"} 0.0
zm_monitor_mmap_last_frame_score{id="6",name="Cats"} 0.0
# HELP zm_monitor_mmap_last_read_index ZM Monitor MMAP field last_read_index
# TYPE zm_monitor_mmap_last_read_index gauge
zm_monitor_mmap_last_read_index{id="1",name="FrontPorch"} 753676.0
zm_monitor_mmap_last_read_index{id="3",name="DiningRoom"} 752301.0
zm_monitor_mmap_last_read_index{id="4",name="LivingRoom"} 752246.0
zm_monitor_mmap_last_read_index{id="5",name="BasementDoorRm"} 1.886224e+06
zm_monitor_mmap_last_read_index{id="6",name="Cats"} 144793.0
# HELP zm_monitor_mmap_last_write_index ZM Monitor MMAP field last_write_index
# TYPE zm_monitor_mmap_last_write_index gauge
zm_monitor_mmap_last_write_index{id="1",name="FrontPorch"} 2.0
zm_monitor_mmap_last_write_index{id="3",name="DiningRoom"} 3.0
zm_monitor_mmap_last_write_index{id="4",name="LivingRoom"} 3.0
zm_monitor_mmap_last_write_index{id="5",name="BasementDoorRm"} 0.0
zm_monitor_mmap_last_write_index{id="6",name="Cats"} 4.0
# HELP zm_monitor_mmap_state ZM Monitor MMAP field state
# TYPE zm_monitor_mmap_state gauge
zm_monitor_mmap_state{id="1",name="FrontPorch"} 1.0
zm_monitor_mmap_state{id="3",name="DiningRoom"} 1.0
zm_monitor_mmap_state{id="4",name="LivingRoom"} 1.0
zm_monitor_mmap_state{id="5",name="BasementDoorRm"} 1.0
zm_monitor_mmap_state{id="6",name="Cats"} 1.0
# HELP zm_monitor_mmap_active ZM Monitor MMAP field active
# TYPE zm_monitor_mmap_active gauge
zm_monitor_mmap_active{id="1",name="FrontPorch"} 1.0
zm_monitor_mmap_active{id="3",name="DiningRoom"} 1.0
zm_monitor_mmap_active{id="4",name="LivingRoom"} 1.0
zm_monitor_mmap_active{id="5",name="BasementDoorRm"} 1.0
zm_monitor_mmap_active{id="6",name="Cats"} 1.0
# HELP zm_monitor_mmap_format ZM Monitor MMAP field format
# TYPE zm_monitor_mmap_format gauge
zm_monitor_mmap_format{id="1",name="FrontPorch"} 1.0
zm_monitor_mmap_format{id="3",name="DiningRoom"} 1.0
zm_monitor_mmap_format{id="4",name="LivingRoom"} 1.0
zm_monitor_mmap_format{id="5",name="BasementDoorRm"} 1.0
zm_monitor_mmap_format{id="6",name="Cats"} 1.0
# HELP zm_monitor_mmap_signal ZM Monitor MMAP field signal
# TYPE zm_monitor_mmap_signal gauge
zm_monitor_mmap_signal{id="1",name="FrontPorch"} 1.0
zm_monitor_mmap_signal{id="3",name="DiningRoom"} 1.0
zm_monitor_mmap_signal{id="4",name="LivingRoom"} 1.0
zm_monitor_mmap_signal{id="5",name="BasementDoorRm"} 1.0
zm_monitor_mmap_signal{id="6",name="Cats"} 1.0
# HELP zm_monitor_mmap_heartbeat_time_age_seconds Seconds since value of ZM Monitor MMAP field heartbeat_time
# TYPE zm_monitor_mmap_heartbeat_time_age_seconds gauge
zm_monitor_mmap_heartbeat_time_age_seconds{id="1",name="FrontPorch"} 0.0
zm_monitor_mmap_heartbeat_time_age_seconds{id="3",name="DiningRoom"} 0.0
zm_monitor_mmap_heartbeat_time_age_seconds{id="4",name="LivingRoom"} 0.0
zm_monitor_mmap_heartbeat_time_age_seconds{id="5",name="BasementDoorRm"} 0.0
zm_monitor_mmap_heartbeat_time_age_seconds{id="6",name="Cats"} 0.0
# HELP zm_monitor_mmap_last_read_time_age_seconds Seconds since value of ZM Monitor MMAP field last_read_time
# TYPE zm_monitor_mmap_last_read_time_age_seconds gauge
zm_monitor_mmap_last_read_time_age_seconds{id="1",name="FrontPorch"} 0.0
zm_monitor_mmap_last_read_time_age_seconds{id="3",name="DiningRoom"} 0.0
zm_monitor_mmap_last_read_time_age_seconds{id="4",name="LivingRoom"} 0.0
zm_monitor_mmap_last_read_time_age_seconds{id="5",name="BasementDoorRm"} 0.0
zm_monitor_mmap_last_read_time_age_seconds{id="6",name="Cats"} 0.0
# HELP zm_monitor_mmap_last_write_time_age_seconds Seconds since value of ZM Monitor MMAP field last_write_time
# TYPE zm_monitor_mmap_last_write_time_age_seconds gauge
zm_monitor_mmap_last_write_time_age_seconds{id="1",name="FrontPorch"} 0.0
zm_monitor_mmap_last_write_time_age_seconds{id="3",name="DiningRoom"} 0.0
zm_monitor_mmap_last_write_time_age_seconds{id="4",name="LivingRoom"} 0.0
zm_monitor_mmap_last_write_time_age_seconds{id="5",name="BasementDoorRm"} 0.0
zm_monitor_mmap_last_write_time_age_seconds{id="6",name="Cats"} 0.0
# HELP zm_monitor_mmap_startup_time_age_seconds Seconds since value of ZM Monitor MMAP field startup_time
# TYPE zm_monitor_mmap_startup_time_age_seconds gauge
zm_monitor_mmap_startup_time_age_seconds{id="1",name="FrontPorch"} 75550.0
zm_monitor_mmap_startup_time_age_seconds{id="3",name="DiningRoom"} 14541.0
zm_monitor_mmap_startup_time_age_seconds{id="4",name="LivingRoom"} 14541.0
zm_monitor_mmap_startup_time_age_seconds{id="5",name="BasementDoorRm"} 75548.0
zm_monitor_mmap_startup_time_age_seconds{id="6",name="Cats"} 14493.0
# HELP zm_zmes_websocket_response_time_seconds ZMES websocket server response time to version request, and status response as a label
# TYPE zm_zmes_websocket_response_time_seconds gauge
zm_zmes_websocket_response_time_seconds{status="Success"} 0.007719278335571289
# HELP zm_daemon_check ZM daemon check
# TYPE zm_daemon_check gauge
zm_daemon_check 1.0
# HELP zm_query_time_seconds Time taken to collect data from ZM
# TYPE zm_query_time_seconds gauge
zm_query_time_seconds 1.4675686359405518
```

## ZoneMinder 1.38 Changes

ZoneMinder 1.38.0 introduced several breaking changes that affect this exporter:

* **`Enabled` field is always 0.** ZM 1.38 replaced the single `Enabled` boolean with the `Capturing` field (`None`/`Ondemand`/`Always`). The exporter now derives `zm_monitor_enabled` from `Capturing != 'None'` when the `Capturing` field is present.
* **`Function` split into three fields.** The single `Function` field (`Monitor`/`Modect`/`Record`/`Mocord`/`Nodect`) has been split into `Capturing`, `Analysing`, and `Recording`. The exporter exposes both the legacy `zm_monitor_function` StateSet and the new `zm_monitor_capturing`, `zm_monitor_analysing`, and `zm_monitor_recording` StateSets.
* **`DecodingEnabled` replaced by `Decoding`.** The boolean `DecodingEnabled` has been replaced by a 5-value enum `Decoding` (`None`/`Ondemand`/`KeyFrames`/`KeyFrames+Ondemand`/`Always`). The exporter exposes both the legacy `zm_monitor_decoding_enabled` gauge and the new `zm_monitor_decoding` StateSet.
* **New per-monitor feature flags.** ZM 1.38 adds `JanusEnabled`, `Go2RTCEnabled`, `RTSP2WebEnabled`, `MQTT_Enabled`, and `ONVIF_Event_Listener` fields, exposed as 0/1 gauge metrics.
* **Shared memory struct format changed.** The SharedData struct grew from 760 to 872 bytes with new fields (image_count, latitude, longitude, additional bools and timestamps, janus_pin). The exporter uses a [fork of pyzm](https://github.com/jantman/pyzm/tree/zm-1.38-compat) that auto-detects the struct version.

## Development

Clone the repo, then in your clone:

```
python3 -mvenv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Release Process

Tag the repo. [GitHub Actions](https://github.com/jantman/prometheus-synology-api-exporter/actions) will run a Docker build, push to Docker Hub and GHCR (GitHub Container Registry), and create a release on the repo.
