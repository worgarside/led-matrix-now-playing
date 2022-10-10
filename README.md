# RGB LED Matrix: Now Playing

## Components

- [Pi Zero W](https://www.raspberrypi.com/products/raspberry-pi-zero-w/)
- [Adafruit RGB Matrix Bonnet for Raspberry Pi](https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi)
- [64x64 RGB LED Matrix Panel](https://www.adafruit.com/product/5407)

# Setup
- Install the matrix drivers and dependencies
  ```bash
  curl https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/main/rgb-matrix.sh >rgb-matrix.sh
  sudo bash rgb-matrix.sh
  ```
  - The source for this is [an Adafruit guide](https://learn.adafruit.com/adafruit-rgb-matrix-bonnet-for-raspberry-pi/)
- Install the Python dependencies
  ```bash
  sudo pip install -r requirements.txt
  ```
  - The dependencies needs to be installed as root because the script needs to be run as root to allow use of the matrix
- Grant `root` read and write permissions to the `crt_artwork` directory
  ```bash
  sudo chmod -R 777 /home/pi/crt_artwork/
  ```
  - Again, this is because the script will be run as root
- Install the service file for auto-running the script on boot
  ```bash
  cd service
  sudo bash install.sh
  ```
  - This will enable and start the service
