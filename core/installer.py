import tempfile
import subprocess
import os
import logging
import threading
import requests
from .downloader import Downloader

class InstallerProcess(threading.Thread):
    """Thread class for handling the installation process"""
    
    def __init__(self, progress_callback=None, status_callback=None, completion_callback=None):
        """Initialize the installer process"""
        super().__init__()
        self.daemon = True
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.completion_callback = completion_callback
        self.running = False
        logging.info("InstallerProcess initialized")
        self.downloader = Downloader(progress_callback, status_callback)

    def run(self):
        """Run the installation process"""
        try:
            logging.info("Starting installation process")
            self.running = True
            
            # Simulate indeterminate progress at start
            if self.progress_callback:
                self.progress_callback(None)
            
            # Get version info directly from api.ascendara.app
            try:
                response = requests.get('https://api.ascendara.app', timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if 'appVer' in data and data.get('status') == 'OK':
                        version = data['appVer']
                        # Use direct GitHub download URL
                        url = f'https://github.com/tagoWorks/ascendara/releases/download/{version}/Ascendara.Setup.{version}.exe'
                        download_path = os.path.join(tempfile.gettempdir(), f"AscendaraInstaller_{version}.exe")
                        
                        if self.status_callback:
                            self.status_callback("Downloading Ascendara...")
                        
                        local_file = self.downloader.download_file(url, download_path)
                        
                        if not os.path.exists(local_file) or os.path.getsize(local_file) == 0:
                            raise Exception("Download verification failed")
                        
                        if self.status_callback:
                            self.status_callback("Running installer...")
                        if self.progress_callback:
                            self.progress_callback(None)  # Switch to indeterminate mode
                        
                        process = subprocess.Popen([local_file], shell=True)
                        process.wait()
                        
                        if process.returncode == 0:
                            if self.status_callback:
                                self.status_callback("Installation complete!")
                            if self.completion_callback:
                                self.completion_callback(True)
                            return
                        else:
                            raise Exception(f"Installation failed with code {process.returncode}")
                    
            except Exception as e:
                logging.error(f"Primary download failed: {str(e)}")
                if self.status_callback:
                    self.status_callback("Primary download failed, trying backup...")
            
            # Fallback: find the setup in GitHub's latest release, in case the API is down
            download_path = os.path.join(tempfile.gettempdir(), "AscendaraInstaller.exe")

            try:
                release = requests.get(
                    'https://api.github.com/repos/Ascendara/ascendara/releases/latest',
                    headers={'Accept': 'application/vnd.github+json'},
                    timeout=15
                )
                release.raise_for_status()
                url = next(
                    asset['browser_download_url']
                    for asset in release.json().get('assets', [])
                    if asset.get('name', '').startswith('Ascendara.Setup.') and asset['name'].endswith('.exe')
                )
                if self.status_callback:
                    self.status_callback("Downloading Ascendara...")
                
                local_file = self.downloader.download_file(url, download_path)
                
                if not os.path.exists(local_file) or os.path.getsize(local_file) == 0:
                    raise Exception("Download verification failed")
                
                if self.status_callback:
                    self.status_callback("Running installer...")
                if self.progress_callback:
                    self.progress_callback(None)  # Switch to indeterminate mode
                
                process = subprocess.Popen([local_file], shell=True)
                process.wait()
                
                if process.returncode == 0:
                    if self.status_callback:
                        self.status_callback("Installation complete!")
                    if self.completion_callback:
                        self.completion_callback(True)
                else:
                    raise Exception(f"Installation failed with code {process.returncode}")
                    
            except Exception as e:
                logging.error(f"Backup download failed: {str(e)}")
                if self.status_callback:
                    self.status_callback("Download failed. Please try again later.")
                if self.completion_callback:
                    self.completion_callback(False)
        
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Installation error: {error_msg}")
            if self.status_callback:
                self.status_callback(f"Error: {error_msg}")
            if self.completion_callback:
                self.completion_callback(False)
        finally:
            self.running = False
