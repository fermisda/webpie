BUILD_DIR = $(HOME)/build/webpie
TAR_DIR = /tmp/$(USER)
TAR_FILE = $(TAR_DIR)/webpie_$(VERSION).tar

all:
	make VERSION=`python webpie/Version.py` all_with_version_defined
	
clean:
	make VERSION=`python webpie/Version.py` clean_with_version_defined

clean_with_version_defined:
	rm -rf $(BUILD_DIR) $(TAR_FILE)

all_with_version_defined:	tarball
	
    
build: $(BUILD_DIR)
	cd webpie; make BUILD_DIR=$(BUILD_DIR) build
	cd samples; make BUILD_DIR=$(BUILD_DIR) build
	cd bin; make BUILD_DIR=$(BUILD_DIR) build
	cp LICENSE $(BUILD_DIR)
    
tarball: clean build $(TAR_DIR)
	cd $(BUILD_DIR); tar cf $(TAR_FILE) *
	@echo 
	@echo Tar file $(TAR_FILE) is ready
	@echo 


$(BUILD_DIR):
	mkdir -p $@
    
$(TAR_DIR):
	mkdir -p $@

