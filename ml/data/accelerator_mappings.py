"""
Accelerator SKU to hardware model mappings for AWS, Azure, and GCP.
"""

# AWS instance family to accelerator mapping
AWS_ACCELERATOR_MAP = {
    # NVIDIA GPUs
    "g6": {"vendor": "nvidia", "family": "L4", "model": "L4", "memory_mib": 24576},
    "g6e": {"vendor": "nvidia", "family": "L40S", "model": "L40S", "memory_mib": 49152},
    "g5": {"vendor": "nvidia", "family": "A10G", "model": "A10G", "memory_mib": 24576},
    "g5g": {
        "vendor": "nvidia",
        "family": "T4G",
        "model": "T4 Tensor Core",
        "memory_mib": 16384,
    },
    "g4dn": {
        "vendor": "nvidia",
        "family": "T4",
        "model": "T4 Tensor Core",
        "memory_mib": 16384,
    },
    "g4ad": {
        "vendor": "amd",
        "family": "Radeon Pro V520",
        "model": "Radeon Pro V520",
        "memory_mib": 8192,
    },
    "g3": {
        "vendor": "nvidia",
        "family": "M60",
        "model": "Tesla M60",
        "memory_mib": 8192,
    },
    "p5": {
        "vendor": "nvidia",
        "family": "H100",
        "model": "H100 SXM5",
        "memory_mib": 81920,
    },
    "p5en": {
        "vendor": "nvidia",
        "family": "H200",
        "model": "H200 SXM",
        "memory_mib": 143360,
    },
    "p4d": {
        "vendor": "nvidia",
        "family": "A100",
        "model": "A100 40GB",
        "memory_mib": 40960,
    },
    "p4de": {
        "vendor": "nvidia",
        "family": "A100",
        "model": "A100 80GB",
        "memory_mib": 81920,
    },
    "p3": {"vendor": "nvidia", "family": "V100", "model": "V100", "memory_mib": 16384},
    "p3dn": {
        "vendor": "nvidia",
        "family": "V100",
        "model": "V100 32GB",
        "memory_mib": 32768,
    },
    "p2": {"vendor": "nvidia", "family": "K80", "model": "K80", "memory_mib": 12288},
    # AWS ASICs
    "inf1": {
        "vendor": "aws",
        "family": "Inferentia",
        "model": "Inferentia",
        "memory_mib": None,
    },
    "inf2": {
        "vendor": "aws",
        "family": "Inferentia",
        "model": "Inferentia2",
        "memory_mib": None,
    },
    "trn1": {
        "vendor": "aws",
        "family": "Trainium",
        "model": "Trainium",
        "memory_mib": None,
    },
    "trn1n": {
        "vendor": "aws",
        "family": "Trainium",
        "model": "Trainium",
        "memory_mib": None,
    },
    "dl1": {
        "vendor": "intel",
        "family": "Habana Gaudi",
        "model": "Gaudi",
        "memory_mib": 32768,
    },
    "dl2q": {
        "vendor": "intel",
        "family": "Habana Gaudi",
        "model": "Gaudi2",
        "memory_mib": 98304,
    },
    # Fractional GPU instances
    "g6f": {
        "vendor": "nvidia",
        "family": "L4",
        "model": "L4",
        "memory_mib": 24576,
        "fractional": True,
    },
}

# AWS GPU count patterns (most have 1, 2, 4, 8, 16)
AWS_GPU_COUNT_MAP = {
    "g6.xlarge": 1,
    "g6.2xlarge": 1,
    "g6.4xlarge": 1,
    "g6.8xlarge": 1,
    "g6.12xlarge": 4,
    "g6.16xlarge": 1,
    "g6.24xlarge": 4,
    "g6.48xlarge": 8,
    "g6e.xlarge": 1,
    "g6e.2xlarge": 1,
    "g6e.4xlarge": 1,
    "g6e.8xlarge": 1,
    "g6e.12xlarge": 4,
    "g6e.16xlarge": 1,
    "g6e.24xlarge": 4,
    "g6e.48xlarge": 8,
    "g5.xlarge": 1,
    "g5.2xlarge": 1,
    "g5.4xlarge": 1,
    "g5.8xlarge": 1,
    "g5.12xlarge": 4,
    "g5.16xlarge": 1,
    "g5.24xlarge": 4,
    "g5.48xlarge": 8,
    "g4dn.xlarge": 1,
    "g4dn.2xlarge": 1,
    "g4dn.4xlarge": 1,
    "g4dn.8xlarge": 1,
    "g4dn.12xlarge": 4,
    "g4dn.16xlarge": 1,
    "g4dn.metal": 8,
    "p5.48xlarge": 8,
    "p5en.48xlarge": 8,
    "p4d.24xlarge": 8,
    "p4de.24xlarge": 8,
    "p3.2xlarge": 1,
    "p3.8xlarge": 4,
    "p3.16xlarge": 8,
    "p3dn.24xlarge": 8,
    "p2.xlarge": 1,
    "p2.8xlarge": 8,
    "p2.16xlarge": 16,
    "inf1.xlarge": 1,
    "inf1.2xlarge": 1,
    "inf1.6xlarge": 4,
    "inf1.24xlarge": 16,
    "inf2.xlarge": 1,
    "inf2.8xlarge": 1,
    "inf2.24xlarge": 6,
    "inf2.48xlarge": 12,
    "trn1.2xlarge": 1,
    "trn1.32xlarge": 16,
    "trn1n.32xlarge": 16,
    "dl1.24xlarge": 8,
    "dl2q.24xlarge": 8,
    "g6f.large": 0,  # 0.125 GPU share
    "g6f.xlarge": 0,
    "g6f.2xlarge": 0,
    "g6f.4xlarge": 0,
    "g6f.8xlarge": 1,
}

# Azure Standard_N* series to accelerator mapping
AZURE_ACCELERATOR_MAP = {
    # NVIDIA GPUs
    "A100": {
        "vendor": "nvidia",
        "family": "A100",
        "model": "A100 80GB",
        "memory_mib": 81920,
    },
    "H100": {
        "vendor": "nvidia",
        "family": "H100",
        "model": "H100",
        "memory_mib": 81920,
    },
    "H200": {
        "vendor": "nvidia",
        "family": "H200",
        "model": "H200",
        "memory_mib": 143360,
    },
    "T4": {"vendor": "nvidia", "family": "T4", "model": "T4", "memory_mib": 16384},
    "A10": {"vendor": "nvidia", "family": "A10", "model": "A10", "memory_mib": 24576},
    "V100": {
        "vendor": "nvidia",
        "family": "V100",
        "model": "V100",
        "memory_mib": 16384,
    },
    "K80": {"vendor": "nvidia", "family": "K80", "model": "K80", "memory_mib": 12288},
    "M60": {"vendor": "nvidia", "family": "M60", "model": "M60", "memory_mib": 8192},
    "P40": {"vendor": "nvidia", "family": "P40", "model": "P40", "memory_mib": 24576},
    "P100": {
        "vendor": "nvidia",
        "family": "P100",
        "model": "P100",
        "memory_mib": 16384,
    },
    # AMD GPUs
    "MI300X": {
        "vendor": "amd",
        "family": "MI300X",
        "model": "MI300X",
        "memory_mib": 196608,
    },
    "V620": {
        "vendor": "amd",
        "family": "Radeon Pro V620",
        "model": "Radeon Pro V620",
        "memory_mib": 32768,
    },
    "V710": {
        "vendor": "amd",
        "family": "Radeon Pro V710",
        "model": "Radeon Pro V710",
        "memory_mib": 32768,
    },
}

# Azure SKU patterns to GPU count (simplified; actual logic in classifier)
AZURE_GPU_PATTERNS = {
    "NC": {"base_gpu": 1, "multipliers": {"6": 1, "12": 2, "24": 4}},
    "ND": {"base_gpu": 1, "multipliers": {"40": 8, "96": 8}},
    "NV": {"base_gpu": 1, "fractional": True},  # NV can have fractional shares
}

# GCP machine type to accelerator mapping
GCP_ACCELERATOR_MAP = {
    # A3 series (H100/H200)
    "a3-highgpu": {
        "vendor": "nvidia",
        "family": "H100",
        "model": "H100 80GB",
        "memory_mib": 81920,
    },
    "a3-megagpu": {
        "vendor": "nvidia",
        "family": "H100",
        "model": "H100 80GB",
        "memory_mib": 81920,
    },
    "a3-edgegpu": {
        "vendor": "nvidia",
        "family": "H100",
        "model": "H100 NVL",
        "memory_mib": 94208,
    },
    "a3-ultra": {
        "vendor": "nvidia",
        "family": "H200",
        "model": "H200",
        "memory_mib": 143360,
    },
    # A2 series (A100)
    "a2-highgpu": {
        "vendor": "nvidia",
        "family": "A100",
        "model": "A100 40GB",
        "memory_mib": 40960,
    },
    "a2-ultragpu": {
        "vendor": "nvidia",
        "family": "A100",
        "model": "A100 80GB",
        "memory_mib": 81920,
    },
    "a2-megagpu": {
        "vendor": "nvidia",
        "family": "A100",
        "model": "A100 40GB",
        "memory_mib": 40960,
    },
    # G2 series (L4)
    "g2-standard": {
        "vendor": "nvidia",
        "family": "L4",
        "model": "L4",
        "memory_mib": 24576,
    },
    # TPU
    "tpu": {
        "vendor": "google",
        "family": "TPU",
        "model": "TPU v5e",
        "memory_mib": 16384,
    },
}

# GCP GPU count from machine suffix (-1g, -2g, -4g, -8g, -16g)
GCP_GPU_COUNT_PATTERNS = {
    "-1g": 1,
    "-2g": 2,
    "-4g": 4,
    "-8g": 8,
    "-16g": 16,
    # G2 specific patterns
    "g2-standard-4": 1,
    "g2-standard-8": 1,
    "g2-standard-12": 1,
    "g2-standard-16": 1,
    "g2-standard-24": 2,
    "g2-standard-32": 1,
    "g2-standard-48": 4,
    "g2-standard-96": 8,
}
