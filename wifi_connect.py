def wifi_connect():
    import network
    import pod_config as cfg
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("connecting to network...")
        wlan.connect(cfg.WIFI_NAME, cfg.WIFI_PWD)
        while not wlan.isconnected():
            pass
    print("network config: ", wlan.ifconfig())

