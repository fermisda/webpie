FILES = \
	HTTPServer.py		Version.py		uid.py \
	WebPieSessionApp.py	WPApp.py WPSessionApp.py\
	WebPieApp.py		__init__.py py3.py
	
LIB_DIR = $(BUILD_DIR)/webpie

build: $(LIB_DIR)
	cp $(FILES) $(LIB_DIR)
	cp -R webob $(LIB_DIR)
	#cp -R jinja2 $(LIB_DIR)
    
$(LIB_DIR):
	mkdir -p $@

    
