FILES = \
    hello_world.py         permissions.py        standalone_session_app.py   time_app.py   time_count.py   time_hello_split.py  time_returns.py \
	hello_world_server.py  standalone_server.py  standalone_threaded_app.py  time_args.py  time_fields.py  time_index.py        uwsgi_app.py
	
DST_DIR = $(BUILD_DIR)/samples

build: $(DST_DIR)
	cp $(FILES) $(DST_DIR)
	cd $(DST_DIR); chmod ugo+x $(FILES)
    
$(DST_DIR):
	mkdir -p $@

    
