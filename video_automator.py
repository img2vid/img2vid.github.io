#!/usr/bin/env python3
"""
Web automation tool for processing files through pgformatter, balcon.exe,
and the img2vid service. This version converts the text to a WAV audio file
and uploads the audio file to the final service.

This version automatically detects the .txt and image file from a target folder
and finds balcon.exe from the system's PATH.

Requires:
- selenium
- webdriver-manager
- pyautogui
- balcon.exe (must be in the system's PATH)

Install Python libraries with:
pip install selenium webdriver-manager pyautogui
"""
import time
import os
import zipfile
import glob
import subprocess
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class AutomationTool:
    """
    A class to automate the process of text cleaning, text-to-speech conversion,
    and video creation.
    """
    def __init__(self, target_folder_path, download_dir=None):
        """
        Initialize the automation tool.

        Args:
            target_folder_path (str): Path to the folder containing the .txt and image files.
            download_dir (str, optional): Directory for downloads.
                                        Defaults to the user's Downloads folder.
        """
        self.target_folder = os.path.abspath(target_folder_path)
        self.download_dir = download_dir or str(Path.home() / "Downloads")
        self.desktop_dir = str(Path.home() / "Desktop")

        self.driver = None
        self.zip_file_path = None
        self.extracted_txt_file = None
        self.audio_file_path = None  # This will store the path to the generated .wav file

        # --- Initial File and Executable Verification ---
        if not os.path.isdir(self.target_folder):
            raise FileNotFoundError(f"Target folder not found: {self.target_folder}")

        # Check for balcon.exe in PATH
        if not shutil.which("balcon"):
            raise FileNotFoundError("balcon.exe not found in system PATH. Please add it to your environment variables.")
        print("Found balcon.exe in system PATH.")

        # Automatically find .txt file in the target folder
        txt_files = glob.glob(os.path.join(self.target_folder, "*.txt"))
        if not txt_files:
            raise FileNotFoundError(f"No .txt file found in {self.target_folder}")
        if len(txt_files) > 1:
            print(f"Warning: Multiple .txt files found. Using the first one: {os.path.basename(txt_files[0])}")
        self.txt_file_path = txt_files[0]
        print(f"Found text file: {os.path.basename(self.txt_file_path)}")

        # Automatically find image file (.jpg, .jpeg, .png) in the target folder
        image_files = []
        for ext in ("*.jpg", "*.jpeg", "*.png"):
            image_files.extend(glob.glob(os.path.join(self.target_folder, ext)))
        
        if not image_files:
            raise FileNotFoundError(f"No image file (.jpg, .jpeg, .png) found in {self.target_folder}")
        if len(image_files) > 1:
            print(f"Warning: Multiple image files found. Using the first one: {os.path.basename(image_files[0])}")
        self.image_file_path = image_files[0]
        print(f"Found image file: {os.path.basename(self.image_file_path)}")


    def setup_driver(self):
        """Setup the Chrome WebDriver with specific download preferences."""
        print("Setting up WebDriver...")
        chrome_options = Options()
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.maximize_window()

    def wait_for_element(self, by, value, timeout=30):
        """A helper function to wait for a web element to be present and clickable."""
        return WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((by, value))
        )

    def step1_pgformatter_process(self):
        """Step 1: Process the initial txt file through pgformatter."""
        print("Step 1: Processing file through pgformatter...")
        self.driver.get("https://img2vid.github.io/pgformatter/")
        
        # Upload the text file
        choose_files_btn = self.wait_for_element(By.XPATH, "//input[@type='file']")
        choose_files_btn.send_keys(self.txt_file_path)
        print(f"Selected file: {self.txt_file_path}")
        
        # Wait for the upload to register
        time.sleep(5)
        
        # Click the download button
        download_btn = self.wait_for_element(By.XPATH, "//button[contains(text(), 'Download Cleaned Files (ZIP)')]")
        download_btn.click()
        print("Clicked download button. Waiting for download to complete...")

        # Wait for the ZIP file to appear in the downloads directory
        end_time = time.time() + 60  # Wait for up to 60 seconds
        while time.time() < end_time:
            zip_files = glob.glob(os.path.join(self.download_dir, "*.zip"))
            if zip_files:
                latest_zip = max(zip_files, key=os.path.getctime)
                # Check if the file was created recently
                if time.time() - os.path.getctime(latest_zip) < 15:
                    self.zip_file_path = latest_zip
                    print(f"ZIP file downloaded: {self.zip_file_path}")
                    return
            time.sleep(1)
            
        raise Exception("ZIP file download timed out or was not found.")

    def step2_extract_zip(self):
        """Step 2: Extract the downloaded ZIP file to the Desktop."""
        if not self.zip_file_path:
            raise Exception("Cannot extract, ZIP file path is not set.")
            
        print("Step 2: Extracting ZIP file to Desktop...")
        zip_name = os.path.splitext(os.path.basename(self.zip_file_path))[0]
        extract_dir = os.path.join(self.desktop_dir, f"extracted_{zip_name}")

        with zipfile.ZipFile(self.zip_file_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print(f"ZIP extracted to: {extract_dir}")

        # Find the cleaned .txt file within the extracted contents
        txt_files = glob.glob(os.path.join(extract_dir, "**", "*.txt"), recursive=True)
        if not txt_files:
            raise Exception("No .txt file found in the extracted ZIP archive.")
            
        self.extracted_txt_file = txt_files[0]
        print(f"Found extracted .txt file: {self.extracted_txt_file}")

    def step3_convert_to_audio(self):
        """Step 3: Convert the cleaned .txt file to a .wav file using balcon.exe."""
        if not self.extracted_txt_file:
            raise Exception("No extracted .txt file available for audio conversion.")

        print("Step 3: Converting .txt file to .wav audio using balcon.exe...")
        
        txt_dir = os.path.dirname(self.extracted_txt_file)
        txt_basename = os.path.splitext(os.path.basename(self.extracted_txt_file))[0]
        
        # Define the explicit output path for the .wav file
        self.audio_file_path = os.path.join(txt_dir, f"{txt_basename}.wav")
        
        # Build the command for balcon.exe (found in PATH)
        # -f: input file
        # -w: output WAV file
        cmd = ["balcon", "-f", self.extracted_txt_file, "-w", self.audio_file_path]
        print(f"Running command: {' '.join(cmd)}")

        try:
            # Execute the command
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True, # This will raise CalledProcessError if balcon returns a non-zero exit code
                timeout=300 # 5-minute timeout
            )
            print(f"Balcon stdout: {result.stdout}")

        except subprocess.TimeoutExpired:
            raise Exception("Balcon.exe timed out after 5 minutes.")
        except subprocess.CalledProcessError as e:
            print(f"Balcon stderr: {e.stderr}")
            raise Exception(f"Balcon.exe failed with return code {e.returncode}.")
        except Exception as e:
            raise Exception(f"An unexpected error occurred while running balcon.exe: {e}")

        # Verify that the .wav file was created
        if not os.path.exists(self.audio_file_path):
            raise FileNotFoundError(f"Audio file was not created at the expected path: {self.audio_file_path}")
            
        print(f"Audio file created successfully: {self.audio_file_path}")

    def step4_upload_to_img2vid(self):
        """Step 4: Upload the image and the generated .wav audio file to img2vid."""
        if not self.audio_file_path:
            raise Exception("Cannot proceed, audio file path is not set.")

        print("Step 4: Processing through img2vid with audio...")
        self.driver.get("https://img2vid.github.io")
        time.sleep(3)

        # Find all file input elements
        file_inputs = self.driver.find_elements(By.XPATH, "//input[@type='file']")
        if len(file_inputs) < 2:
            raise Exception("Could not find two file input elements on the page.")

        # Upload the image file to the first input
        print(f"Uploading image file: {self.image_file_path}")
        image_input = file_inputs[0]
        image_input.send_keys(self.image_file_path)
        time.sleep(2)

        # Upload the WAV audio file to the second input
        print(f"Uploading audio file: {self.audio_file_path}")
        audio_input = file_inputs[1]
        audio_input.send_keys(self.audio_file_path)
        time.sleep(2)

        # Click 'Start All Jobs'
        start_btn = self.wait_for_element(By.XPATH, "//button[contains(text(), 'Start') and contains(text(), 'Jobs')]")
        start_btn.click()
        print("Started processing jobs on img2vid...")

    def step5_wait_for_video_and_download(self):
        """Step 5: Wait for video processing to complete and then download it."""
        print("Step 5: Waiting for video processing to complete...")
        
        # Wait for the 'Download Video' button to appear and be enabled
        try:
            download_video_btn = WebDriverWait(self.driver, 3600).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Download Video')]"))
            )
            print("Download Video button is ready!")
        except Exception:
            raise Exception("Download Video button did not become clickable within the 1-hour time limit.")

        # Click the download button
        download_video_btn.click()
        print("Clicked Download Video button. The download should begin shortly.")
        time.sleep(10) # Give ample time for the download to initiate

    def run_automation(self):
        """Run the complete automation process from start to finish."""
        try:
            print("--- Starting Automation Process ---")
            self.setup_driver()
            
            self.step1_pgformatter_process()
            self.step2_extract_zip()
            self.step3_convert_to_audio()
            self.step4_upload_to_img2vid()
            self.step5_wait_for_video_and_download()
            
            print("\n--- Automation Completed Successfully! ---")

        except Exception as e:
            print(f"\n--- An error occurred during automation: {e} ---")
            # The 'finally' block will still execute to close the browser
            raise

        finally:
            if self.driver:
                print("Closing browser in 5 seconds...")
                time.sleep(5)
                self.driver.quit()

def main():
    """Main function to get user input and run the automation tool."""
    print("--- Web Automation Tool ---")
    print("Please provide the path to the folder with your files.")
    
    try:
        target_folder = input("Enter the path to your target folder: ").strip().strip('"\'')
        
        download_dir_input = input("Enter download directory (or press Enter for default 'Downloads' folder): ").strip().strip('"\'')
        download_dir = download_dir_input if download_dir_input else None

        tool = AutomationTool(target_folder, download_dir)
        tool.run_automation()

    except FileNotFoundError as e:
        print(f"\nERROR: A required file or executable was not found. Please check the path or your setup. Details: {e}")
    except Exception as e:
        print(f"\nFATAL ERROR: The automation failed unexpectedly. Details: {e}")

if __name__ == "__main__":
    main()
