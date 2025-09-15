"""
VLM Processor Module for Gauge Reading Extraction
Handles Vision Language Model operations for processing gauge images
"""

from transformers import AutoProcessor, AutoModelForImageTextToText, AutoModelForCausalLM, AutoTokenizer
from PIL import Image
import torch
import json
import logging
import traceback
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pick GPU if available, otherwise fallback to CPU
device = "cuda" if torch.cuda.is_available() else "cpu"
class VLMProcessor:
    """Vision Language Model processor for gauge reading extraction"""
    
    def __init__(self):
        self.model_vlm = None
        self.processor_vlm = None
        self.model_llm = None
        self.tokenizer_vlm = None
        self.is_initialized = False
        
        # Model configurations
        self.model_id_vlm = "LiquidAI/LFM2-VL-450M"
        # self.model_id_llm = "LiquidAI/LFM2-350M"
        
        # Conversation template for gauge reading
        self.conversation_template = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": None},  # Will be replaced with actual image
                    {
                        "type": "text",
                        "text": """TASK: Extract numeric readings from three digital gauges in this image.

GAUGE IDENTIFICATION (left to right):
- LEFT gauge (black/dark): rain_gauge (units: mm)
- MIDDLE gauge (white with blue header): thermometer (units: °C)
- RIGHT gauge (white/red circular): pressure_gauge (units: bar)

READING INSTRUCTIONS:
1. Focus ONLY on the main numeric display on each gauge's LCD/LED screen
2. Read the complete number including decimal points if present
3. Ignore any secondary displays, unit labels, or interface elements
4. If a gauge shows multiple numbers, use the largest/primary display

OUTPUT FORMAT:
- Return ONLY valid JSON with no additional text, markdown, or formatting
- Use null for unreadable or missing gauges
- Round to maximum 2 decimal places
- Use integers when the value is a whole number

REQUIRED JSON STRUCTURE:
{
 "rain_gauge": <number|null>,
 "thermometer": <number|null>,
 "pressure_gauge": <number|null>
}

Analyze the image now and return the JSON response."""
                    },
                ],
            },
        ]
    
    def initialize_models(self):
        """Initialize VLM models - should be called once at startup"""
        try:
            logger.info("Initializing VLM models...")
            
            # Load VLM model and processor
            logger.info(f"Loading VLM model: {self.model_id_vlm}")
            self.model_vlm = AutoModelForImageTextToText.from_pretrained(
                self.model_id_vlm,
                device_map={"": device},  # Force CPU for stability
                torch_dtype=torch.float32,
                trust_remote_code=True
            )
            
            self.processor_vlm = AutoProcessor.from_pretrained(
                self.model_id_vlm, 
                trust_remote_code=True
            )
            
            # # Load LLM model and tokenizer
            # logger.info(f"Loading LLM model: {self.model_id_llm}")
            # self.model_llm = AutoModelForCausalLM.from_pretrained(
            #     self.model_id_llm,
            #     device_map="auto",
            #     torch_dtype="bfloat16",
            #     trust_remote_code=True
            # )
            
            # self.tokenizer_vlm = AutoTokenizer.from_pretrained(self.model_id_llm)
            
            self.is_initialized = True
            logger.info("VLM models initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize VLM models: {str(e)}")
            logger.error(traceback.format_exc())
            self.is_initialized = False
            raise
    
    def process_image(self, image_path=None, pil_image=None):
        """
        Process an image and extract gauge readings
        
        Args:
            image_path (str): Path to image file
            pil_image (PIL.Image): PIL Image object
            
        Returns:
            dict: Processing result with gauge readings and metadata
        """
        if not self.is_initialized:
            return {
                'success': False,
                'error': 'VLM models not initialized',
                'gauge_readings': None,
                'raw_response': None
            }
        
        try:
            # Load and prepare image
            if pil_image is not None:
                image = pil_image
            elif image_path is not None:
                image = Image.open(image_path)
            else:
                return {
                    'success': False,
                    'error': 'No image provided',
                    'gauge_readings': None,
                    'raw_response': None
                }
            
            # Ensure RGB format
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            # Prepare conversation with image
            conversation = self.conversation_template.copy()
            conversation[0]["content"][0]["image"] = image
            
            # Process with VLM
            logger.info("Processing image with VLM...")
            inputs = self.processor_vlm.apply_chat_template(
                conversation,
                add_generation_prompt=True,
                return_tensors="pt",
                return_dict=True,
                tokenize=True,
            ).to(self.model_vlm.device)
            
            # Generate response
            outputs = self.model_vlm.generate(**inputs, max_new_tokens=512)
            decoded = self.processor_vlm.batch_decode(outputs, skip_special_tokens=True)[0]
            
            # Extract assistant's response
            if "assistant" in decoded:
                response = decoded.split("assistant", 1)[1].strip()
            else:
                response = decoded.strip()
            
            logger.info(f"VLM Raw Response: {response}")
            
            # Parse JSON response
            gauge_readings = self.parse_gauge_response(response)
            
            return {
                'success': True,
                'error': None,
                'gauge_readings': gauge_readings,
                'raw_response': response
            }
            
        except Exception as e:
            error_msg = f"Error processing image: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            return {
                'success': False,
                'error': error_msg,
                'gauge_readings': None,
                'raw_response': None
            }
    
    def parse_gauge_response(self, response):
        """
        Parse the VLM response and extract gauge readings
        
        Args:
            response (str): Raw response from VLM
            
        Returns:
            dict: Parsed gauge readings or None if parsing fails
        """
        try:
            # Try to find JSON in the response
            response = response.strip()
            
            # Look for JSON-like structure
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response[start_idx:end_idx + 1]
                gauge_data = json.loads(json_str)
                
                # Validate expected structure
                expected_keys = ['rain_gauge', 'thermometer', 'pressure_gauge']
                if all(key in gauge_data for key in expected_keys):
                    return gauge_data
                else:
                    logger.warning(f"Missing expected keys in response: {gauge_data}")
                    return gauge_data  # Return partial data
            
            # If no valid JSON found, return None
            logger.warning(f"Could not parse JSON from response: {response}")
            return None
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error parsing gauge response: {str(e)}")
            return None

# Global VLM processor instance
vlm_processor = None

def get_vlm_processor():
    """Get or create global VLM processor instance"""
    global vlm_processor
    if vlm_processor is None:
        vlm_processor = VLMProcessor()
    return vlm_processor

def initialize_vlm():
    """Initialize VLM models globally"""
    processor = get_vlm_processor()
    if not processor.is_initialized:
        processor.initialize_models()
    return processor

def process_image_for_gauges(image_path=None, pil_image=None):
    """
    Convenience function to process image and get gauge readings
    
    Args:
        image_path (str): Path to image file
        pil_image (PIL.Image): PIL Image object
        
    Returns:
        dict: Processing result
    """
    processor = get_vlm_processor()
    return processor.process_image(image_path=image_path, pil_image=pil_image)

if __name__ == "__main__":
    # Test the VLM processor
    print("Testing VLM Processor...")
    
    # Initialize
    processor = initialize_vlm()
    
    # Test with sample image (if available)
    test_image_path = "merged_gauges_csv/merged_0001_caliper_2.27mm_temperature_27.2C_pressure_0.97bar.jpg"
    
    if os.path.exists(test_image_path):
        result = process_image_for_gauges(image_path=test_image_path)
        print(f"Test Result: {json.dumps(result, indent=2)}")
    else:
        print(f"Test image not found: {test_image_path}")