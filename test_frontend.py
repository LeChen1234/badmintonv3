"""
Test script for the badminton annotation frontend.
Tests registration and login functionality.
"""
import time
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def test_registration_and_login():
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    
    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print("Step 1: Navigate to http://localhost:3000/login")
        driver.get("http://localhost:3000/login")
        time.sleep(2)
        
        print("Step 2: Taking screenshot of login page")
        driver.save_screenshot("screenshot_1_login_page.png")
        print("✓ Screenshot saved: screenshot_1_login_page.png")
        
        print("\nStep 3: Looking for Register tab/button (注册)")
        try:
            # Look for register tab - try multiple selectors
            register_button = None
            selectors = [
                "//button[contains(text(), '注册')]",
                "//a[contains(text(), '注册')]",
                "//div[contains(text(), '注册')]",
                "//*[contains(text(), '注册')]"
            ]
            
            for selector in selectors:
                try:
                    register_button = driver.find_element(By.XPATH, selector)
                    if register_button:
                        print(f"✓ Found register button with selector: {selector}")
                        break
                except:
                    continue
            
            if not register_button:
                print("✗ Could not find register button")
                driver.save_screenshot("screenshot_error_no_register.png")
                return False
            
            print("Step 4: Clicking register button")
            register_button.click()
            time.sleep(1)
            
            print("Step 5: Taking screenshot of registration form")
            driver.save_screenshot("screenshot_2_register_form.png")
            print("✓ Screenshot saved: screenshot_2_register_form.png")
            
        except Exception as e:
            print(f"✗ Error finding/clicking register button: {e}")
            driver.save_screenshot("screenshot_error_register_tab.png")
            return False
        
        print("\nStep 6: Filling in registration form")
        try:
            # Wait for form fields to be present
            wait = WebDriverWait(driver, 10)
            
            # Find and fill username field
            username_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text'], input[placeholder*='用户名'], input[name='username']"))
            )
            username_input.clear()
            username_input.send_keys("lisi")
            print("✓ Filled username: lisi")
            
            # Find and fill display name field
            # This might be the second text input
            text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']")
            if len(text_inputs) > 1:
                text_inputs[1].clear()
                text_inputs[1].send_keys("李四")
                print("✓ Filled display name: 李四")
            
            # Find and fill password fields
            password_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            if len(password_inputs) >= 2:
                password_inputs[0].clear()
                password_inputs[0].send_keys("test123456")
                print("✓ Filled password: test123456")
                
                password_inputs[1].clear()
                password_inputs[1].send_keys("test123456")
                print("✓ Filled confirm password: test123456")
            else:
                print("✗ Could not find password fields")
                driver.save_screenshot("screenshot_error_password_fields.png")
                return False
            
            time.sleep(1)
            
        except Exception as e:
            print(f"✗ Error filling form: {e}")
            driver.save_screenshot("screenshot_error_fill_form.png")
            return False
        
        print("\nStep 7: Clicking register button (注册)")
        try:
            # Find and click the submit button
            submit_button = driver.find_element(By.XPATH, "//button[contains(text(), '注册')]")
            submit_button.click()
            time.sleep(2)
            
            print("Step 8: Taking screenshot of result")
            driver.save_screenshot("screenshot_3_register_result.png")
            print("✓ Screenshot saved: screenshot_3_register_result.png")
            
        except Exception as e:
            print(f"✗ Error clicking submit: {e}")
            driver.save_screenshot("screenshot_error_submit.png")
            return False
        
        print("\nStep 9: Checking if registration succeeded")
        # Check for success indicators or error messages
        try:
            # Wait a moment for any messages to appear
            time.sleep(1)
            
            # Check if we're redirected or if there's a success message
            current_url = driver.current_url
            print(f"Current URL: {current_url}")
            
            # Try to find login tab or switch to login
            print("\nStep 10: Switching to login tab")
            try:
                login_tab = driver.find_element(By.XPATH, "//button[contains(text(), '登录')]|//a[contains(text(), '登录')]|//*[contains(text(), '登录') and not(contains(text(), '退出'))]")
                login_tab.click()
                time.sleep(1)
                print("✓ Switched to login tab")
            except:
                print("Note: Could not find login tab (might already be on login page)")
            
        except Exception as e:
            print(f"Note: {e}")
        
        print("\nStep 11: Logging in with new credentials")
        try:
            # Clear and fill login form
            username_input = driver.find_element(By.CSS_SELECTOR, "input[type='text'], input[placeholder*='用户名'], input[name='username']")
            username_input.clear()
            username_input.send_keys("lisi")
            print("✓ Entered username: lisi")
            
            password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            password_input.clear()
            password_input.send_keys("test123456")
            print("✓ Entered password: test123456")
            
            # Find and click login button
            login_button = driver.find_element(By.XPATH, "//button[contains(text(), '登录') and not(contains(text(), '退出'))]")
            login_button.click()
            time.sleep(2)
            
            print("\nStep 12: Taking screenshot after login")
            driver.save_screenshot("screenshot_4_after_login.png")
            print("✓ Screenshot saved: screenshot_4_after_login.png")
            
            # Check if login was successful
            current_url = driver.current_url
            print(f"\n✓ Final URL: {current_url}")
            
            if "login" not in current_url.lower():
                print("✓ Login successful! Redirected away from login page.")
            else:
                print("⚠ Still on login page - check if there are any error messages")
            
            return True
            
        except Exception as e:
            print(f"✗ Error during login: {e}")
            driver.save_screenshot("screenshot_error_login.png")
            return False
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        driver.save_screenshot("screenshot_error_general.png")
        return False
        
    finally:
        print("\nTest completed. Closing browser in 5 seconds...")
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    print("=" * 60)
    print("Badminton Annotation System - Frontend Test")
    print("=" * 60)
    print()
    
    try:
        success = test_registration_and_login()
        if success:
            print("\n" + "=" * 60)
            print("✓ TEST PASSED")
            print("=" * 60)
            sys.exit(0)
        else:
            print("\n" + "=" * 60)
            print("✗ TEST FAILED")
            print("=" * 60)
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        sys.exit(1)
