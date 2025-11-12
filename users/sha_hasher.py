import os
import binascii # Used for converting bytes to hex strings and vice-versa

# --- Configuration for PIN Hashing ---
SALT_BYTES = 16  # 16 bytes = 32 hexadecimal characters for salt
HASH_OUTPUT_BYTES = 32 # SHA-256 produces a 32-byte hash

# --- SHA-256 Constants ---

# Initial 32-bit Hash Values (first 32 bits of the fractional parts of the square roots of the first 8 primes) ie.h0 to h7
_H_INITIAL = (
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
)

# 64 32-bit Round Constants (first 32 bits of the fractional parts of the cube roots of the first 64 primes) ie.k0 to k63
_K_CONSTANTS = (
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
)

# --- Bitwise Helper Functions (32-bit operations) ---
# Python integers have arbitrary precision, so we must explicitly mask with 0xFFFFFFFF (which is 2^32 - 1) to simulate 32-bit arithmetic.

def _rotr(x, n): # Right Rotate
    """ROTR^n(x)"""
    return ((x >> n) | (x << (32 - n))) & 0xFFFFFFFF

def _shr(x, n): # Right Shift
    """SHR^n(x)"""
    return (x >> n) & 0xFFFFFFFF

def _ch(x, y, z): # Choice Function
    """Ch(x, y, z) = (x AND y) XOR (NOT x AND z)"""
    return (x & y) ^ ((~x) & z) & 0xFFFFFFFF # (~x) needs to be masked as well

def _maj(x, y, z): # Majority Function
    """Maj(x, y, z) = (x AND y) XOR (x AND z) XOR (y AND z)"""
    return (x & y) ^ (x & z) ^ (y & z)

def _sigma0(x): # Capital Sigma 0
    """Σ0(x) = ROTR^2(x) XOR ROTR^13(x) XOR ROTR^22(x)"""
    return _rotr(x, 2) ^ _rotr(x, 13) ^ _rotr(x, 22)

def _sigma1(x): # Capital Sigma 1
    """Σ1(x) = ROTR^6(x) XOR ROTR^11(x) XOR ROTR^25(x)"""
    return _rotr(x, 6) ^ _rotr(x, 11) ^ _rotr(x, 25)

def _sigma0_prime(x): # Lowercase Sigma 0 (for Message Schedule)
    """σ0(x) = ROTR^7(x) XOR ROTR^18(x) XOR SHR^3(x)"""
    return _rotr(x, 7) ^ _rotr(x, 18) ^ _shr(x, 3)

def _sigma1_prime(x): # Lowercase Sigma 1 (for Message Schedule)
    """σ1(x) = ROTR^17(x) XOR ROTR^19(x) XOR SHR^10(x)"""
    return _rotr(x, 17) ^ _rotr(x, 19) ^ _shr(x, 10)

def _add_mod32(*args):
    """Performs addition modulo 2^32 for any number of 32-bit integers."""
    total = sum(args)
    return total & 0xFFFFFFFF

# --- SHA-256 Core Logic ---

def _sha256_pad_message(message_bytes):
    """
    Pads the input message according to SHA-256 (NIST FIPS 180-4) standard.
    """
    # 1. Append a single '1' bit
    # This means adding 0x80 to the message (10000000 binary)
    padded_message = bytearray(message_bytes)
    padded_message.append(0x80)

    # 2. Append '0' bits until length is 448 mod 512
    # The length is in BITS. 512 bits = 64 bytes. 448 bits = 56 bytes.
    # We need to find how many zeros to append to reach `length % 64 == 56`.
    # Current length in bytes
    current_length_bytes = len(padded_message)
    # How many bytes needed to reach the next 56-byte boundary
    bytes_to_append = (56 - (current_length_bytes % 64)) % 64
    if bytes_to_append == 0: # If it's already at 56 mod 64, need a full new block of 64 bytes
        bytes_to_append = 64

    # Append zero bytes
    padded_message.extend(bytearray(bytes_to_append))

    # 3. Append original message length as a 64-bit big-endian integer
    original_length_bits = len(message_bytes) * 8
    # Convert to 8 bytes (64 bits) big-endian
    length_bytes = original_length_bits.to_bytes(8, 'big')
    padded_message.extend(length_bytes)

    return padded_message

def _sha256_compress(h_values, message_block_words):
    """
    The SHA-256 compression function for a single 512-bit message block.
    """
    # 1. Initialize working variables a, b, c, d, e, f, g, h
    a, b, c, d, e, f, g, h = h_values

    # 2. Prepare the Message Schedule W (64 32-bit words)
    W = [0] * 64
    # Copy first 16 words from the message block
    for t in range(16):
        W[t] = message_block_words[t]
    # Extend to 64 words
    for t in range(16, 64):
        W[t] = _add_mod32(_sigma1_prime(W[t-2]), W[t-7], _sigma0_prime(W[t-15]), W[t-16])

    # 3. Main Compression Loop (64 rounds)
    for t in range(64):
        T1 = _add_mod32(h, _sigma1(e), _ch(e, f, g), _K_CONSTANTS[t], W[t])
        T2 = _add_mod32(_sigma0(a), _maj(a, b, c))

        h = g
        g = f
        f = e
        e = _add_mod32(d, T1)
        d = c
        c = b
        b = a
        a = _add_mod32(T1, T2)

    # 4. Update intermediate hash values (H0-H7)
    h_values = (
        _add_mod32(h_values[0], a),
        _add_mod32(h_values[1], b),
        _add_mod32(h_values[2], c),
        _add_mod32(h_values[3], d),
        _add_mod32(h_values[4], e),
        _add_mod32(h_values[5], f),
        _add_mod32(h_values[6], g),
        _add_mod32(h_values[7], h)
    )
    return h_values

def _calculate_sha256(message_bytes):
    """
    Calculates the SHA-256 hash of the input message bytes.
    """
    # 1. Pre-processing: Pad the message
    padded_message = _sha256_pad_message(message_bytes)

    # 2. Initialize hash values H0-H7
    h_values = list(_H_INITIAL) # Convert to list to make it mutable

    # 3. Process the message in 512-bit (64-byte) chunks
    # Each chunk is 16 32-bit words
    for i in range(0, len(padded_message), 64):
        chunk = padded_message[i : i+64]
        message_block_words = [0] * 16
        for j in range(16):
            # Convert 4 bytes from chunk to a 32-bit integer (big-endian)
            message_block_words[j] = int.from_bytes(chunk[j*4 : (j+1)*4], 'big')
        
        # Apply the compression function for this block
        h_values = _sha256_compress(h_values, message_block_words)
    
    # 4. Final Output: Concatenate the final H values
    final_hash_bytes = bytearray()
    for h_val in h_values:
        # Convert each 32-bit integer back to 4 bytes (big-endian)
        final_hash_bytes.extend(h_val.to_bytes(4, 'big'))

    return final_hash_bytes

# --- Public API for PIN Hashing using Custom SHA-256 ---

def hash_pin(pin_string):
    """
    Hashes a PIN string using our custom SHA-256 with a random salt.
    The output format is: "salt_in_hex$hash_in_hex"
    """
    if not isinstance(pin_string, str):
        raise TypeError("PIN must be a string")

    # Generate a random salt (cryptographically strong random bytes from OS)
    salt = os.urandom(SALT_BYTES)

    # Encode the PIN string to bytes (essential for hashing)
    pin_bytes = pin_string.encode('utf-8')

    # Combine salt and PIN bytes. This is the input to our custom SHA-256.
    combined_data_for_hashing = salt + pin_bytes

    # Apply our custom SHA-256
    hashed_output_bytes = _calculate_sha256(combined_data_for_hashing)

    # Convert salt and the hash output to hexadecimal strings for storage
    return f"{binascii.hexlify(salt).decode('ascii')}${binascii.hexlify(hashed_output_bytes).decode('ascii')}"

def check_pin(pin_string, hashed_pin_from_db):
    """
    Verifies a PIN string against a stored hashed PIN using our custom SHA-256.
    """
    if not isinstance(pin_string, str):
        raise TypeError("PIN must be a string")
    if not isinstance(hashed_pin_from_db, str):
        return False # Stored value is not a string, cannot check

    try:
        # Split the stored hash string to extract the salt and the stored hash output
        salt_hex, stored_hash_hex = hashed_pin_from_db.split('$', 1)
        # Convert hex strings back to bytes
        salt = binascii.unhexlify(salt_hex)
        stored_hash_bytes = binascii.unhexlify(stored_hash_hex)
    except (ValueError, binascii.Error):
        # Format is incorrect or hex decoding failed, so it's not a valid hash
        return False

    # Encode the provided PIN string to bytes
    pin_bytes = pin_string.encode('utf-8')

    # Recombine the extracted salt with the provided PIN bytes
    combined_data_for_hashing = salt + pin_bytes

    # Apply our custom SHA-256 to the new combination
    newly_hashed_output_bytes = _calculate_sha256(combined_data_for_hashing)

    # Compare the newly generated hash output with the stored hash output
    return newly_hashed_output_bytes == stored_hash_bytes

