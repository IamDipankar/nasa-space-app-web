#!/usr/bin/env python3
"""
Test script to validate the district/upazila implementation
"""

def test_html_structure():
    """Test if HTML has the correct district and upazila dropdowns"""
    try:
        with open('statics/index.html', 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Check for district dropdown
        if 'id="district"' in html_content and 'Select a district' in html_content:
            print("✓ District dropdown found in HTML")
        else:
            print("✗ District dropdown missing from HTML")
            return False
        
        # Check for upazila dropdown
        if 'id="upazila"' in html_content and 'Select a upazila' in html_content:
            print("✓ Upazila dropdown found in HTML")
        else:
            print("✗ Upazila dropdown missing from HTML")
            return False
        
        # Check if old location input is removed
        if 'id="location"' in html_content:
            print("✗ Old location input still exists in HTML")
            return False
        else:
            print("✓ Old location input successfully removed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error reading HTML file: {e}")
        return False

def test_css_structure():
    """Test if CSS has the correct form-select styles"""
    try:
        with open('statics/styles.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
        
        if '.form-select' in css_content:
            print("✓ form-select CSS class found")
        else:
            print("✗ form-select CSS class missing")
            return False
        
        if '.form-select:disabled' in css_content:
            print("✓ form-select disabled state CSS found")
        else:
            print("✗ form-select disabled state CSS missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error reading CSS file: {e}")
        return False

def test_javascript_structure():
    """Test if JavaScript has the correct functionality"""
    try:
        with open('statics/script.js', 'r', encoding='utf-8') as f:
            js_content = f.read()
        
        # Check for district and upazila elements
        if 'getElementById(\'district\')' in js_content:
            print("✓ District element reference found in JavaScript")
        else:
            print("✗ District element reference missing from JavaScript")
            return False
        
        if 'getElementById(\'upazila\')' in js_content:
            print("✓ Upazila element reference found in JavaScript")
        else:
            print("✗ Upazila element reference missing from JavaScript")
            return False
        
        # Check for API calls
        if '/api/districts' in js_content:
            print("✓ Districts API call found in JavaScript")
        else:
            print("✗ Districts API call missing from JavaScript")
            return False
        
        if '/api/upazilas/' in js_content:
            print("✓ Upazilas API call found in JavaScript")
        else:
            print("✗ Upazilas API call missing from JavaScript")
            return False
        
        # Check if old location references are removed
        if 'locationInput' in js_content:
            print("✗ Old locationInput references still exist in JavaScript")
            return False
        else:
            print("✓ Old locationInput references successfully removed")
        
        return True
        
    except Exception as e:
        print(f"✗ Error reading JavaScript file: {e}")
        return False

def test_backend_structure():
    """Test if backend has the correct API endpoints and request handling"""
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            main_content = f.read()
        
        # Check for API endpoints
        if '@app.get("/api/districts")' in main_content:
            print("✓ Districts API endpoint found in main.py")
        else:
            print("✗ Districts API endpoint missing from main.py")
            return False
        
        if '@app.get("/api/upazilas/{district_name}")' in main_content:
            print("✓ Upazilas API endpoint found in main.py")
        else:
            print("✗ Upazilas API endpoint missing from main.py")
            return False
        
        # Check request model
        if 'upazila: str = None' in main_content and 'district: str' in main_content:
            print("✓ AnalysisRequest model updated with district/upazila fields")
        else:
            print("✗ AnalysisRequest model not properly updated")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error reading main.py file: {e}")
        return False

def test_router_structure():
    """Test if router has the correct functionality"""
    try:
        with open('models/anlyzers/router.py', 'r', encoding='utf-8') as f:
            router_content = f.read()
        
        # Check for new functions
        if 'def get_districts_list():' in router_content:
            print("✓ get_districts_list function found in router.py")
        else:
            print("✗ get_districts_list function missing from router.py")
            return False
        
        if 'def get_upazilas_by_district(' in router_content:
            print("✓ get_upazilas_by_district function found in router.py")
        else:
            print("✗ get_upazilas_by_district function missing from router.py")
            return False
        
        # Check for fixed filtering logic
        if '[(upz[\'UPAZILA_NA\'] == upazila_name) & (upz[\'DISTRICT_N\'] == district_name)]' in router_content:
            print("✓ Fixed filtering logic found in router.py")
        else:
            print("✗ Filtering logic not properly fixed in router.py")
            return False
        
        return True
        
    except Exception as e:
        print(f"✗ Error reading router.py file: {e}")
        return False

if __name__ == "__main__":
    print("Testing District/Upazila Implementation...")
    print("=" * 50)
    
    tests = [
        ("HTML Structure", test_html_structure),
        ("CSS Structure", test_css_structure),
        ("JavaScript Structure", test_javascript_structure),
        ("Backend Structure", test_backend_structure),
        ("Router Structure", test_router_structure),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        print("-" * 20)
        if test_func():
            passed += 1
            print(f"✓ {test_name} PASSED")
        else:
            print(f"✗ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Implementation looks good.")
    else:
        print("❌ Some tests failed. Please review the implementation.")