import sys
import torch, transformers, cv2

print("python      ", sys.version.split()[0])
print("torch       ", torch.__version__)
print("cuda avail  ", torch.cuda.is_available())
if torch.cuda.is_available():
    print("device      ", torch.cuda.get_device_name(0))
    print("capability  ", torch.cuda.get_device_capability(0))
    print("vram GB     ", round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 1))
    x = torch.randn(2048, 2048, device="cuda")
    print("fp32 matmul ", bool(torch.isfinite((x @ x).sum()).item()))
    print("fp16 matmul ", bool(torch.isfinite((x.half() @ x.half()).sum()).item()))
print("transformers", transformers.__version__)
print("opencv      ", cv2.__version__)

from transformers import GroundingDinoForObjectDetection, Owlv2ForObjectDetection, AutoProcessor
print("model classes OK: GroundingDino, OWLv2")
