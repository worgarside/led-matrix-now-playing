PYTHON_VERSION ?= 3.11

create-env:
	virtualenv -p $(PYTHON_VERSION) .venv
	$(MAKE) install

install:
	.venv/bin/pip install -r requirements.txt

service:
	sudo systemctl stop rgb_led_matrix.service
	cp service/rgb_led_matrix.service /etc/systemd/system/
	echo "Service file copied to /etc/systemd/system/rgb_led_matrix.service"
	sudo systemctl enable rgb_led_matrix.service
	sudo systemctl start rgb_led_matrix.service

update:
	git add .
	git stash save "Stash before update @ $(shell date)"
	git pull --prune
	@$(MAKE) install
