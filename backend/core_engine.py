import cv2
import imagehash
from PIL import Image
import os

def generate_video_dna(video_path, num_frames=5):
    """
    Video se specific frames nikalta hai aur unka Perceptual Hash (pHash) banata hai.
    Yeh hash video crop ya compress hone par bhi almost same rehta hai.
    """
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return []

    video = cv2.VideoCapture(video_path)
    total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if total_frames == 0:
        print("Error: Could not read frames from the video.")
        video.release()
        return []

    # Calculate intervals to extract evenly spaced frames
    interval = max(1, total_frames // num_frames)
    dna_hashes = []

    for i in range(num_frames):
        # Frame ki position set karo
        video.set(cv2.CAP_PROP_POS_FRAMES, i * interval)
        success, frame = video.read()
        
        if success:
            # OpenCV frame (BGR) ko PIL Image (RGB) mein convert karo
            cv2_im_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil_im = Image.fromarray(cv2_im_rgb)
            
            # Perceptual Hash generate karo aur string format mein save karo
            frame_hash = imagehash.phash(pil_im)
            dna_hashes.append(str(frame_hash))

    video.release()
    return dna_hashes

def compare_videos(official_dna, suspected_video_path, match_threshold=5):
    """
    Suspected video ka DNA nikalta hai aur official DNA se compare karta hai.
    Hamming distance use karta hai. Threshold 5 ka matlab hai minor edits (crop/color) ignore honge.
    """
    if not official_dna:
        return {"error": "Official DNA is empty. Cannot compare."}

    suspected_dna_strings = generate_video_dna(suspected_video_path)
    
    if not suspected_dna_strings:
        return {"error": "Could not generate DNA for the suspected video."}
    
    # Strings ko wapas imagehash objects mein convert karo taaki math operation ho sake
    official_hashes = [imagehash.hex_to_hash(h) for h in official_dna]
    suspected_hashes = [imagehash.hex_to_hash(h) for h in suspected_dna_strings]
    
    match_score = 0
    
    # Dono videos ke frames ko one-by-one compare karo
    # Zip functions unhe pairs mein laata hai: (Frame 1 vs Frame 1), (Frame 2 vs Frame 2)
    for o_hash, s_hash in zip(official_hashes, suspected_hashes):
        # Hamming distance: Kitne bits alag hain. 0 means exactly identical.
        difference = o_hash - s_hash
        
        # Agar difference threshold ke andar hai, toh hum ise match maante hain
        if difference <= match_threshold:
            match_score += 1

    total_frames_checked = min(len(official_hashes), len(suspected_hashes))
    
    # Agar 60% se zyada frames match ho gaye, toh video pirated hai!
    is_pirated = match_score >= (total_frames_checked * 0.6)
    confidence_percentage = (match_score / total_frames_checked) * 100 if total_frames_checked > 0 else 0
    
    return {
        "is_pirated": is_pirated,
        "frames_matched": match_score,
        "total_frames_checked": total_frames_checked,
        "confidence": f"{confidence_percentage:.2f}%"
    }

# ---------------------------------------------------------
# Local Testing Block (Hackathon mein testing ke liye best)
# ---------------------------------------------------------
if __name__ == "__main__":
    print("--- OpticShield Core Engine Test ---")
    
    # Testing ke liye 2 dummy video paths (Aap apni asli .mp4 files ka path daalna)
    dummy_official_video = "test_assets/official.mp4" 
    dummy_pirated_video = "test_assets/pirated.mp4"
    
    # Step 1: Ek dummy file banate hain check karne ke liye taaki code run ho jaye
    # Agar files nahi hain toh hum create kar lenge for testing purposes
    if not os.path.exists("test_assets"):
        os.makedirs("test_assets")
        
    # Sirf test karne ke liye agar aapke paas actual video files hain toh unhe 'test_assets' folder mein rakhein
    if os.path.exists(dummy_official_video) and os.path.exists(dummy_pirated_video):
        print("\n[1] Generating Official DNA...")
        official_dna_signature = generate_video_dna(dummy_official_video)
        print(f"Official DNA: {official_dna_signature}")
        
        print("\n[2] Comparing Suspected Video with Official DNA...")
        result = compare_videos(official_dna_signature, dummy_pirated_video)
        print(f"Result: {result}")
    else:
        print("\nTest videos not found! Pura engine test karne ke liye 'test_assets' folder mein 'official.mp4' aur 'pirated.mp4' rakh do aur script ko run karo.")