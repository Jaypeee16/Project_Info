#!/usr/bin/env python3
"""
Test suite for passphrase-based key derivation functionality.
Validates PBKDF2 implementation and backward compatibility.
"""

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from secure_journal_app import (
    generate_salt,
    derive_keys_from_passphrase,
    verify_passphrase,
    set_global_keys,
    get_playfair_key,
    get_xor_key,
    PLAYFAIR_KEY,
    XOR_KEY,
)


def test_salt_generation():
    """Test that salt generation produces unique values."""
    print("Test 1: Salt Generation")
    salt1 = generate_salt()
    salt2 = generate_salt()
    
    assert salt1 != salt2, "Salts should be unique"
    assert len(salt1) == 64, f"Salt should be 64 hex chars (32 bytes), got {len(salt1)}"
    assert len(salt2) == 64, f"Salt should be 64 hex chars (32 bytes), got {len(salt2)}"
    print("  ✓ Salt generation works (unique, correct length)")


def test_key_derivation_consistency():
    """Test that same passphrase + salt = same keys."""
    print("\nTest 2: Key Derivation Consistency")
    passphrase = "test_passphrase_12345"
    salt = generate_salt()
    
    keys1 = derive_keys_from_passphrase(passphrase, salt)
    keys2 = derive_keys_from_passphrase(passphrase, salt)
    
    assert keys1 == keys2, "Same passphrase + salt should produce identical keys"
    print("  ✓ Key derivation is deterministic")


def test_key_derivation_uniqueness():
    """Test that different salts = different keys."""
    print("\nTest 3: Key Derivation Uniqueness (per salt)")
    passphrase = "test_passphrase_12345"
    salt1 = generate_salt()
    salt2 = generate_salt()
    
    keys1 = derive_keys_from_passphrase(passphrase, salt1)
    keys2 = derive_keys_from_passphrase(passphrase, salt2)
    
    assert keys1 != keys2, "Different salts should produce different keys"
    print("  ✓ Keys are salt-dependent (prevents rainbow tables)")


def test_passphrase_verification():
    """Test passphrase verification logic."""
    print("\nTest 4: Passphrase Verification")
    passphrase = "my_secret_passphrase"
    salt = generate_salt()
    
    _, _, verification = derive_keys_from_passphrase(passphrase, salt)
    
    # Correct passphrase
    assert verify_passphrase(passphrase, salt, verification), "Correct passphrase should verify"
    print("  ✓ Correct passphrase verifies successfully")
    
    # Wrong passphrase
    assert not verify_passphrase("wrong_passphrase", salt, verification), "Wrong passphrase should not verify"
    print("  ✓ Wrong passphrase fails verification")
    
    # Wrong salt
    wrong_salt = generate_salt()
    assert not verify_passphrase(passphrase, wrong_salt, verification), "Wrong salt should not verify"
    print("  ✓ Wrong salt fails verification")


def test_global_keys():
    """Test global key getters."""
    print("\nTest 5: Global Key Management")
    
    # Before setting passphrase, should use defaults
    default_playfair = get_playfair_key()
    default_xor = get_xor_key()
    assert default_playfair == PLAYFAIR_KEY, "Should use default Playfair key"
    assert default_xor == XOR_KEY, "Should use default XOR key"
    print("  ✓ Default keys used before passphrase setup")
    
    # After setting passphrase
    passphrase = "test_passphrase_12345"
    salt = generate_salt()
    set_global_keys(passphrase, salt)
    
    derived_playfair = get_playfair_key()
    derived_xor = get_xor_key()
    
    assert derived_playfair != PLAYFAIR_KEY, "Should use derived Playfair key"
    assert derived_xor != XOR_KEY, "Should use derived XOR key"
    assert derived_playfair != derived_xor, "Playfair and XOR keys should be different"
    print("  ✓ Derived keys used after passphrase setup")


def test_key_lengths():
    """Test that derived keys have correct lengths."""
    print("\nTest 6: Key Lengths")
    passphrase = "test_passphrase_12345"
    salt = generate_salt()
    
    playfair_key, xor_key, verification = derive_keys_from_passphrase(passphrase, salt)
    
    # Playfair key should be 26 chars (for 5x5 grid)
    assert len(playfair_key) == 26, f"Playfair key should be 26 chars, got {len(playfair_key)}"
    print("  ✓ Playfair key is correct length (26 chars)")
    
    # XOR key should be 30 chars
    assert len(xor_key) == 30, f"XOR key should be 30 chars, got {len(xor_key)}"
    print("  ✓ XOR key is correct length (30 chars)")
    
    # Verification should be hex (64 chars for SHA256)
    assert len(verification) == 64, f"Verification should be 64 hex chars, got {len(verification)}"
    print("  ✓ Verification token is correct length (64 hex chars)")


def test_min_passphrase_length():
    """Test that passphrase length constraint is enforced."""
    print("\nTest 7: Passphrase Minimum Length")
    salt = generate_salt()
    
    # Short passphrases should still work (enforcement is in UI, not crypto)
    try:
        _, _, _ = derive_keys_from_passphrase("short", salt)
        print("  ✓ Short passphrases derive successfully (UI enforces minimum)")
    except ValueError:
        print("  ✗ Should allow short passphrases at crypto level")
        raise


def test_empty_passphrase_error():
    """Test that empty passphrase raises error."""
    print("\nTest 8: Empty Passphrase Error Handling")
    salt = generate_salt()
    
    try:
        derive_keys_from_passphrase("", salt)
        print("  ✗ Should reject empty passphrase")
        assert False
    except ValueError:
        print("  ✓ Empty passphrase rejected with ValueError")


def main():
    """Run all tests."""
    print("=" * 60)
    print("PASSPHRASE KEY DERIVATION TEST SUITE")
    print("=" * 60)
    
    try:
        test_salt_generation()
        test_key_derivation_consistency()
        test_key_derivation_uniqueness()
        test_passphrase_verification()
        test_global_keys()
        test_key_lengths()
        test_min_passphrase_length()
        test_empty_passphrase_error()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED (8/8)")
        print("=" * 60)
        return 0
    except AssertionError as exc:
        print(f"\n✗ TEST FAILED: {exc}")
        return 1
    except Exception as exc:
        print(f"\n✗ UNEXPECTED ERROR: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
