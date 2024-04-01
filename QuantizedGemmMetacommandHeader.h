constexpr unsigned int QUANTIZATION_PARAMETERS_MAX = 4;

enum META_COMMAND_QUANTIZATION_PARAMETERS_TYPE : UINT64
{
    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE_NONE,
    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE_SCALE,
    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE_SCALE_ZEROPOINT,

    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE_COUNT,
};

// -------------------------------------------------------------------------------------------------------------------
// QUANTIZED_GEMM - GE
// 

// Create a quantized GEMM operation. This metacommand works similarly to the GEMM metacommand, but each A/B/C/Output tensor also has an array of
// parameters. The number of quantization parameters and the behavior of the quantization is control by their respective parameters type:
//      META_COMMAND_QUANTIZATION_PARAMETERS_TYPE_NONE: The parameter descs array is empty and the tensor is not quantized.
//      META_COMMAND_QUANTIZATION_PARAMETERS_TYPE_SCALE: The parameter descs array has 1 element (scale) that should be used to dequantize the tensor
//      META_COMMAND_QUANTIZATION_PARAMETERS_TYPE_SCALE_ZEROPOINT: The parameter descs array has 2 elements (scale and zeropoint) that should be used to dequantize the tensor.
//
// Note that unlike classic optional tensors, unused quantization parameters will not be bound at initialization and execution time using a null binding. This means
// that there won't be null bindings in the middle of the quantization parameters. The only tensor that can receive a null binding is the C tensor.

// {1DEB77D1-456E-4793-BF00-0799F6F2CF0D}
static constexpr GUID GUID_QUANTIZED_GEMM =
{ 0x1deb77d1, 0x456e, 0x4793, { 0xbf, 0x0, 0x7, 0x99, 0xf6, 0xf2, 0xcf, 0xd } };

struct META_COMMAND_ATTRIBUTES_QUANTIZED_GEMM
{
    META_COMMAND_PRECISION Precision;
    META_COMMAND_MATRIX_TRANSFORM ATransform;
    META_COMMAND_MATRIX_TRANSFORM BTransform;
    FLOAT Alpha;
    FLOAT Beta;
    META_COMMAND_OPTIONAL_ACTIVATION_DESC Activation;
    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE AQuantizationParametersType;
    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE BQuantizationParametersType;
    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE CQuantizationParametersType;
    META_COMMAND_QUANTIZATION_PARAMETERS_TYPE OutputQuantizationParametersType;
    META_COMMAND_BIND_FLAGS BindFlags;
};

struct META_COMMAND_CREATE_QUANTIZED_GEMM
{
    META_COMMAND_TENSOR_DESC1 ADesc;
    META_COMMAND_TENSOR_DESC1 BDesc;
    META_COMMAND_OPTIONAL_TENSOR_DESC1 CDesc;
    META_COMMAND_OPTIONAL_TENSOR_DESC1 AQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_OPTIONAL_TENSOR_DESC1 BQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_OPTIONAL_TENSOR_DESC1 CQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_OPTIONAL_TENSOR_DESC1 OutputQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_TENSOR_DESC1 OutputDesc;
    META_COMMAND_ATTRIBUTES_QUANTIZED_GEMM Attributes;
};

struct META_COMMAND_INITIALIZE_QUANTIZED_GEMM
{
    D3D12_GPU_DESCRIPTOR_HANDLE AResource;
    D3D12_GPU_DESCRIPTOR_HANDLE BResource;
    D3D12_GPU_DESCRIPTOR_HANDLE CResource;
    D3D12_GPU_DESCRIPTOR_HANDLE AQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE BQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE CQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE OutputQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE PersistentResource;
    D3D12_GPU_DESCRIPTOR_HANDLE TemporaryResource;
};

struct META_COMMAND_EXECUTE_QUANTIZED_GEMM
{
    D3D12_GPU_DESCRIPTOR_HANDLE AResource;
    D3D12_GPU_DESCRIPTOR_HANDLE BResource;
    D3D12_GPU_DESCRIPTOR_HANDLE CResource;
    D3D12_GPU_DESCRIPTOR_HANDLE AQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE BQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE CQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE OutputQuantizationParametersResources[QUANTIZATION_PARAMETERS_MAX];
    D3D12_GPU_DESCRIPTOR_HANDLE OutputResource;
    D3D12_GPU_DESCRIPTOR_HANDLE PersistentResource;
    D3D12_GPU_DESCRIPTOR_HANDLE TemporaryResource;
};

struct META_COMMAND_LAYOUT_SET_QUANTIZED_GEMM
{
    META_COMMAND_TENSOR_LAYOUT1 ALayout;
    META_COMMAND_TENSOR_LAYOUT1 BLayout;
    META_COMMAND_TENSOR_LAYOUT1 CLayout;
    META_COMMAND_TENSOR_LAYOUT1 AQuantizationParametersLayouts[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_TENSOR_LAYOUT1 BQuantizationParametersLayouts[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_TENSOR_LAYOUT1 CQuantizationParametersLayouts[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_TENSOR_LAYOUT1 OutputQuantizationParametersLayouts[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_TENSOR_LAYOUT1 OutputLayout;
};

struct META_COMMAND_QUERY_INPUT_QUANTIZED_GEMM
{
    META_COMMAND_LAYOUT_SET_QUANTIZED_GEMM LayoutSets[QUERY_LAYOUT_SETS_MAX];
    UINT64 LayoutSetCount;

    META_COMMAND_TENSOR_PROTO_DESC ADesc;
    META_COMMAND_TENSOR_PROTO_DESC BDesc;
    META_COMMAND_OPTIONAL_TENSOR_PROTO_DESC CDesc;
    META_COMMAND_OPTIONAL_TENSOR_PROTO_DESC AQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_OPTIONAL_TENSOR_PROTO_DESC BQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_OPTIONAL_TENSOR_PROTO_DESC CQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_OPTIONAL_TENSOR_PROTO_DESC OutputQuantizationParametersDescs[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_TENSOR_PROTO_DESC OutputDesc;

    META_COMMAND_ATTRIBUTES_QUANTIZED_GEMM Attributes;
};

struct META_COMMAND_LAYOUT_SUPPORT_QUANTIZED_GEMM
{
    META_COMMAND_LAYOUT_SUPPORT_LEVEL SupportLevel;
    UINT64 LayoutSetIndex;

    META_COMMAND_LAYOUT_REQUIREMENTS ARequirements;
    META_COMMAND_LAYOUT_REQUIREMENTS BRequirements;
    META_COMMAND_LAYOUT_REQUIREMENTS CRequirements;
    META_COMMAND_LAYOUT_REQUIREMENTS AQuantizationParametersRequirements[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_LAYOUT_REQUIREMENTS BQuantizationParametersRequirements[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_LAYOUT_REQUIREMENTS CQuantizationParametersRequirements[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_LAYOUT_REQUIREMENTS OutputQuantizationParametersRequirements[QUANTIZATION_PARAMETERS_MAX];
    META_COMMAND_LAYOUT_REQUIREMENTS OutputRequirements;
};

struct META_COMMAND_QUERY_OUTPUT_QUANTIZED_GEMM
{
    META_COMMAND_LAYOUT_SUPPORT_QUANTIZED_GEMM Results[QUERY_RESULTS_MAX];
    UINT64 ResultCount;  
};