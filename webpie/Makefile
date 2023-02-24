FILES = \
	__init__.py \
	HTTPServer.py		Version.py		uid.py \
	WPApp.py WPSessionApp.py \
	py3.py yaml_expand.py sanitizers.py
	
LIB_DIR = $(BUILD_DIR)/webpie

build: $(LIB_DIR)
	cp $(FILES) $(LIB_DIR)
	cp -R webob $(LIB_DIR)
	cp -R logs $(LIB_DIR)
    
$(LIB_DIR):
	mkdir -p $@

    
