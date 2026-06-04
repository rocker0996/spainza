"""
Test script for visa path permissions system
"""

import sys
sys.path.insert(0, '.')

from models.user import (
    get_assignable_visa_types,
    can_assign_visa_type,
    ASSIGNABLE_VISA_TYPES_BY_ROLE
)

def test_visa_permissions():
    """Test visa type assignment permissions for all roles."""
    
    print("=" * 70)
    print("TESTING VISA PATH PERMISSIONS SYSTEM")
    print("=" * 70)
    print()
    
    roles_to_test = [
        "management",
        "admin",
        "support",
        "moderator",
        "manager",
        "digital_nomad",
        "golden_visa",
        "user"
    ]
    
    visa_types_to_test = [
        "digital_nomad",
        "golden_visa",
        "citizen",
        "other"
    ]
    
    # Test 1: Check assignable visa types for each role
    print("TEST 1: Available visa paths by role")
    print("-" * 70)
    
    for role in roles_to_test:
        assignable = get_assignable_visa_types(role)
        print(f"\nRole: {role}")
        print(f"   Available paths: {len(assignable)}")
        
        if assignable:
            print(f"   Paths:")
            for visa in assignable:
                print(f"      - {visa['label_ru']} ({visa['value']})")
        else:
            print(f"   [X] No available visa paths")
    
    print("\n" + "=" * 70)
    print()
    
    # Test 2: Check specific permissions
    print("TEST 2: Specific permission checks")
    print("-" * 70)
    
    test_cases = [
        ("management", "digital_nomad", True),
        ("management", "golden_visa", True),
        ("admin", "citizen", True),
        ("support", "digital_nomad", True),
        ("support", "golden_visa", True),
        ("moderator", "other", True),
        ("manager", "digital_nomad", True),
        ("digital_nomad", "golden_visa", False),
        ("golden_visa", "citizen", False),
        ("user", "digital_nomad", False),
    ]
    
    passed = 0
    failed = 0
    
    for role, visa_type, expected in test_cases:
        result = can_assign_visa_type(role, visa_type)
        status = "[PASS]" if result == expected else "[FAIL]"
        
        if result == expected:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | {role:15} -> {visa_type:15} | Expected: {expected}, Got: {result}")
    
    print("\n" + "-" * 70)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 70)
    print()
    
    # Test 3: Verify data structure
    print("TEST 3: Data structure verification")
    print("-" * 70)
    
    print(f"\n[OK] Total roles in system: {len(ASSIGNABLE_VISA_TYPES_BY_ROLE)}")
    print(f"[OK] Total visa types for testing: {len(visa_types_to_test)}")
    
    # Check that all roles have entries
    for role in roles_to_test:
        if role in ASSIGNABLE_VISA_TYPES_BY_ROLE:
            print(f"[OK] Role '{role}' present in mapping")
        else:
            print(f"[X] Role '{role}' MISSING in mapping!")
    
    print("\n" + "=" * 70)
    print()
    
    # Test 4: Check multilingual support
    print("TEST 4: Multilingual support check")
    print("-" * 70)
    
    visa_types = get_assignable_visa_types("management")
    
    if visa_types:
        print("\n[OK] Checking translations:")
        for visa in visa_types:
            has_ru = 'label_ru' in visa and visa['label_ru']
            has_en = 'label_en' in visa and visa['label_en']
            has_value = 'value' in visa and visa['value']
            
            status_ru = "[OK]" if has_ru else "[X]"
            status_en = "[OK]" if has_en else "[X]"
            status_val = "[OK]" if has_value else "[X]"
            
            print(f"   {visa['value']:15} | RU: {status_ru} | EN: {status_en} | Value: {status_val}")
    
    print("\n" + "=" * 70)
    print()
    
    # Summary
    print("FINAL REPORT")
    print("-" * 70)
    
    if failed == 0:
        print("[SUCCESS] ALL TESTS PASSED!")
        print("   Visa path permissions system is working correctly.")
    else:
        print(f"[WARNING] ISSUES FOUND: {failed} test(s) failed")
        print("   Configuration needs review.")
    
    print("=" * 70)
    print()
    
    return failed == 0


if __name__ == "__main__":
    success = test_visa_permissions()
    sys.exit(0 if success else 1)
