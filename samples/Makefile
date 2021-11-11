FILES = \
callable_handler.py  https_server.py     relpath.py                  strict_handler.py   time_count.py              uwsgi_app.py \
function_app.py      lambda_app.py       robots.py                   templates.py        time_count_thread_safe.py  wp_test.py \
getset.py            nested_handlers.py  slow_server.py              test.py             time_handlers.py \
hello_time.py        permissions.py      standalone_server.py        threads_1.py        time_hello_split.py \
hello_world.py       post_client.py      standalone_session_app.py   threads_2.py        time_index.py \
hello_world_wsgi.py  post.py             standalone_threaded_app.py  threads_context.py  time_returns.py \
https.py             post_receiver.py    static_server.py            time_args.py        time_server.py

	
DST_DIR = $(BUILD_DIR)/samples

build: $(DST_DIR)
	cp $(FILES) $(DST_DIR)
	cd $(DST_DIR); chmod ugo+x $(FILES)
    
$(DST_DIR):
	mkdir -p $@

    
