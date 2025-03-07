import tempfile
import subprocess
import os
import logging
import threading
import requests
import hmac
import hashlib
import time
import uuid
from .downloader import Downloader

class InstallerProcess:
    def __init__(self, progress_callback=None, status_callback=None, completion_callback=None):
        self.progress_callback = progress_callback
        self.status_callback = status_callback
        self.completion_callback = completion_callback
        self.downloader = Downloader(progress_callback, status_callback)
        # Generate a unique client ID for this installer instance
        self.client_id = str(uuid.uuid4())
        # In production, this should be set via environment variable
        self.installer_secret = os.environ.get('INSTALLER_SECRET', 'dev_secret_key')

    def start(self):
        thread = threading.Thread(target=self._installation_process)
        thread.daemon = True
        thread.start()

    def _generate_auth_headers(self):
        """Generate authentication headers for LFS API"""
        timestamp = str(int(time.time()))
        message = f"{timestamp}:{self.client_id}"
        signature = hmac.new(
            self.installer_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            'X-Installer-Timestamp': timestamp,
            'X-Installer-Signature': signature,
            'X-Installer-ID': self.client_id
        }

    def _update_download_count(self, is_update=False):
        try:
            # Make a quick request to LFS endpoint with authentication
            params = {'update': '1'} if is_update else {}
            headers = self._generate_auth_headers()
            
            requests.get(
                'https://lfs.ascendara.app/download', 
                params=params,
                headers=headers,
                timeout=2,  # Short timeout since we don't need the response
                stream=True  # Don't download the file
            )
        except:
            # Silently ignore any errors - download count is not critical
            pass

    def _installation_process(self):
        try:
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
                        
                        # Update download count in background with authentication
                        is_update = bool(os.environ.get('ASCENDARA_UPDATE', False))
                        threading.Thread(
                            target=self._update_download_count,
                            args=(is_update,),
                            daemon=True
                        ).start()
                        
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
            
            # Fallback to LFS endpoint
            url = "https://lfs.ascendara.app/download"
            if os.environ.get('ASCENDARA_UPDATE'):
                url += "?update=1"
            download_path = os.path.join(tempfile.gettempdir(), "AscendaraInstaller.exe")
            
            try:
                # Add authentication headers for the download
                headers = self._generate_auth_headers()
                if self.status_callback:
                    self.status_callback("Downloading Ascendara...")
                
                local_file = self.downloader.download_file(url, download_path, headers)
                
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