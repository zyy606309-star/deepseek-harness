/**
 * cb 参数生成器
 * 网易盾无感验证码逆向
 * 版本: v2 - 基于断点分析
 */

// ============ 常量 ============

// 自定义 Base64 字符集
const BASE64_CHARS = 'MB.CfHUzEeJpsuGkgNwhqiSaI4Fd9L6jYKZAxn1/Vml0c5rbXRP+8tD3QTO2vWyo';
const BASE64_PAD = '7';

// 随机字符集 (生成32字符随机串)
const RANDOM_CHARS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz';

// 种子密钥
const SEED_KEY = 'fd6a43ae25f74398b61c03c83be37449';

// S-Box (256字节, 从hex转换)
const SBOX_HEX = 'a7be3f3933fa8c5fcf86c4b6908b569ba1e26c1a6d7cfbf60ae4b00e074a194dac4b73e7f898541159a39d08183b76eedee3ed341e6685d2357440158394b1ff03a9004cbbb5ca7dcb7f41489a16e03dcc9c71eb3c9796685b1d01b4d56193a6e1f1a2470445c191ae49c5d82765dc82c350f263387a24a502fcbf442e2dddaad0e936d9ea22b89275307b42518fbc3a626ba806d4ecd6d725f50cc8c72fefa4551ccd6fc9b2b7ab954f815c7264c6e51f4eaf99885a79892b1b60a0b3526e57ba5d178d370958847eb9fd28f9ce0bc023f4148a2adfe632126769057043d3bd8eda0df7872629f3809ef05310e83113216afe202c460fc23e789f77d1addb5e';

// 变换序列
const TRANSFORM_SEQ = '037606da0296055c';

// code 和插入位置
const CODE = 'vfnv46';
const CODE_POS = [1, 10, 12, 13, 26, 31];

// ============ 工具函数 ============

// Hex 转字节数组
function hexToBytes(hex) {
    const bytes = [];
    for (let i = 0; i < hex.length; i += 2) {
        bytes.push(parseInt(hex.substr(i, 2), 16));
    }
    return bytes;
}

// 转有符号字节
function toSignedByte(val) {
    val = val & 0xFF;
    return val > 127 ? val - 256 : val;
}

// 转无符号字节
function toUnsignedByte(val) {
    return ((val % 256) + 256) % 256;
}

// 生成随机字符串
function randomString(len) {
    let result = '';
    for (let i = 0; i < len; i++) {
        result += RANDOM_CHARS[Math.floor(Math.random() * RANDOM_CHARS.length)];
    }
    return result;
}

// 生成随机字节数组
function randomBytes(len) {
    const result = [];
    for (let i = 0; i < len; i++) {
        result.push(toSignedByte(Math.floor(Math.random() * 256)));
    }
    return result;
}

// 字符串转字节数组 (UTF8)
function stringToBytes(str) {
    const encoded = encodeURIComponent(str);
    const bytes = [];
    for (let i = 0; i < encoded.length; i++) {
        if (encoded[i] === '%') {
            bytes.push(parseInt(encoded.substr(i + 1, 2), 16));
            i += 2;
        } else {
            bytes.push(encoded.charCodeAt(i));
        }
    }
    return bytes.map(toSignedByte);
}

// CRC32
const CRC32_TABLE = [
    0x0, 0x77073096, 0xee0e612c, 0x990951ba, 0x76dc419, 0x706af48f, 0xe963a535, 0x9e6495a3,
    0xedb8832, 0x79dcb8a4, 0xe0d5e91e, 0x97d2d988, 0x9b64c2b, 0x7eb17cbd, 0xe7b82d07, 0x90bf1d91,
    0x1db71064, 0x6ab020f2, 0xf3b97148, 0x84be41de, 0x1adad47d, 0x6ddde4eb, 0xf4d4b551, 0x83d385c7,
    0x136c9856, 0x646ba8c0, 0xfd62f97a, 0x8a65c9ec, 0x14015c4f, 0x63066cd9, 0xfa0f3d63, 0x8d080df5,
    0x3b6e20c8, 0x4c69105e, 0xd56041e4, 0xa2677172, 0x3c03e4d1, 0x4b04d447, 0xd20d85fd, 0xa50ab56b,
    0x35b5a8fa, 0x42b2986c, 0xdbbbc9d6, 0xacbcf940, 0x32d86ce3, 0x45df5c75, 0xdcd60dcf, 0xabd13d59,
    0x26d930ac, 0x51de003a, 0xc8d75180, 0xbfd06116, 0x21b4f4b5, 0x56b3c423, 0xcfba9599, 0xb8bda50f,
    0x2802b89e, 0x5f058808, 0xc60cd9b2, 0xb10be924, 0x2f6f7c87, 0x58684c11, 0xc1611dab, 0xb6662d3d,
    0x76dc4190, 0x1db7106, 0x98d220bc, 0xefd5102a, 0x71b18589, 0x6b6b51f, 0x9fbfe4a5, 0xe8b8d433,
    0x7807c9a2, 0xf00f934, 0x9609a88e, 0xe10e9818, 0x7f6a0dbb, 0x86d3d2d, 0x91646c97, 0xe6635c01,
    0x6b6b51f4, 0x1c6c6162, 0x856530d8, 0xf262004e, 0x6c0695ed, 0x1b01a57b, 0x8208f4c1, 0xf50fc457,
    0x65b0d9c6, 0x12b7e950, 0x8bbeb8ea, 0xfcb9887c, 0x62dd1ddf, 0x15da2d49, 0x8cd37cf3, 0xfbd44c65,
    0x4db26158, 0x3ab551ce, 0xa3bc0074, 0xd4bb30e2, 0x4adfa541, 0x3dd895d7, 0xa4d1c46d, 0xd3d6f4fb,
    0x4369e96a, 0x346ed9fc, 0xad678846, 0xda60b8d0, 0x44042d73, 0x33031de5, 0xaa0a4c5f, 0xdd0d7cc9,
    0x5005713c, 0x270241aa, 0xbe0b1010, 0xc90c2086, 0x5768b525, 0x206f85b3, 0xb966d409, 0xce61e49f,
    0x5edef90e, 0x29d9c998, 0xb0d09822, 0xc7d7a8b4, 0x59b33d17, 0x2eb40d81, 0xb7bd5c3b, 0xc0ba6cad,
    0xedb88320, 0x9abfb3b6, 0x3b6e20c, 0x74b1d29a, 0xead54739, 0x9dd277af, 0x4db2615, 0x73dc1683,
    0xe3630b12, 0x94643b84, 0xd6d6a3e, 0x7a6a5aa8, 0xe40ecf0b, 0x9309ff9d, 0xa00ae27, 0x7d079eb1,
    0xf00f9344, 0x8708a3d2, 0x1e01f268, 0x6906c2fe, 0xf762575d, 0x806567cb, 0x196c3671, 0x6e6b06e7,
    0xfed41b76, 0x89d32be0, 0x10da7a5a, 0x67dd4acc, 0xf9b9df6f, 0x8ebeeff9, 0x17b7be43, 0x60b08ed5,
    0xd6d6a3e8, 0xa1d1937e, 0x38d8c2c4, 0x4fdff252, 0xd1bb67f1, 0xa6bc5767, 0x3fb506dd, 0x48b2364b,
    0xd80d2bda, 0xaf0a1b4c, 0x36034af6, 0x41047a60, 0xdf60efc3, 0xa867df55, 0x316e8eef, 0x4669be79,
    0xcb61b38c, 0xbc66831a, 0x256fd2a0, 0x5268e236, 0xcc0c7795, 0xbb0b4703, 0x220216b9, 0x5505262f,
    0xc5ba3bbe, 0xb2bd0b28, 0x2bb45a92, 0x5cb36a04, 0xc2d7ffa7, 0xb5d0cf31, 0x2cd99e8b, 0x5bdeae1d,
    0x9b64c2b0, 0xec63f226, 0x756aa39c, 0x26d930a, 0x9c0906a9, 0xeb0e363f, 0x72076785, 0x5005713,
    0x95bf4a82, 0xe2b87a14, 0x7bb12bae, 0xcb61b38, 0x92d28e9b, 0xe5d5be0d, 0x7cdcefb7, 0xbdbdf21,
    0x86d3d2d4, 0xf1d4e242, 0x68ddb3f8, 0x1fda836e, 0x81be16cd, 0xf6b9265b, 0x6fb077e1, 0x18b74777,
    0x88085ae6, 0xff0f6a70, 0x66063bca, 0x11010b5c, 0x8f659eff, 0xf862ae69, 0x616bffd3, 0x166ccf45,
    0xa00ae278, 0xd70dd2ee, 0x4e048354, 0x3903b3c2, 0xa7672661, 0xd06016f7, 0x4969474d, 0x3e6e77db,
    0xaed16a4a, 0xd9d65adc, 0x40df0b66, 0x37d83bf0, 0xa9bcae53, 0xdebb9ec5, 0x47b2cf7f, 0x30b5ffe9,
    0xbdbdf21c, 0xcabac28a, 0x53b39330, 0x24b4a3a6, 0xbad03605, 0xcdd70693, 0x54de5729, 0x23d967bf,
    0xb3667a2e, 0xc4614ab8, 0x5d681b02, 0x2a6f2b94, 0xb40bbe37, 0xc30c8ea1, 0x5a05df1b, 0x2d02ef8d
];

function crc32(bytes) {
    let crc = 0xFFFFFFFF;
    for (let i = 0; i < bytes.length; i++) {
        const b = toUnsignedByte(bytes[i]);
        crc = CRC32_TABLE[(crc ^ b) & 0xFF] ^ (crc >>> 8);
    }
    crc = (crc ^ 0xFFFFFFFF) >>> 0;
    return crc.toString(16).padStart(8, '0');
}

// S-Box 查找
const SBOX = hexToBytes(SBOX_HEX);

function sboxLookup(val) {
    const idx = toUnsignedByte(val);
    const result = SBOX[idx];
    return result > 127 ? result - 256 : result;
}

// 双重 S-Box
function doubleSbox(bytes) {
    return bytes.map(b => {
        const s1 = sboxLookup(b);
        const s2 = sboxLookup(s1);
        return s2;
    });
}

// XOR 两个数组
function xorArrays(a, b) {
    const len = a.length;
    const result = [];
    for (let i = 0; i < len; i++) {
        result[i] = toSignedByte(a[i] ^ b[i % b.length]);
    }
    return result;
}

// ADD 两个数组
function addArrays(a, b) {
    const len = a.length;
    const result = [];
    for (let i = 0; i < len; i++) {
        result[i] = toSignedByte(a[i] + b[i % b.length]);
    }
    return result;
}

// ============ 密钥生成 ============

// 扩展到64字节 (循环填充)
function expandTo64(bytes) {
    if (!bytes.length) return new Array(64).fill(0);
    if (bytes.length >= 64) return bytes.slice(0, 64);

    const result = [];
    for (let i = 0; i < 64; i++) {
        result[i] = bytes[i % bytes.length];
    }
    return result;
}

// 生成主密钥 (从种子密钥派生)
function generateMainKey() {
    // 1. 种子密钥转字节
    const seedBytes = stringToBytes(SEED_KEY);

    // 2. 生成4字节随机IV
    const iv = randomBytes(4);

    // 3. 扩展种子到64字节
    const expandedSeed = expandTo64(seedBytes);

    // 4. 扩展IV到64字节
    const expandedIV = expandTo64(iv);

    // 5. XOR 种子和IV (无S-Box!)
    const mainKey = xorArrays(expandedSeed, expandedIV);

    return [mainKey, iv];
}

// ============ 变换函数 ============

// 解析变换序列: "037606da0296055c"
// 03 76 → func3 param=0x76
// 06 da → func6 param=0xda
// 02 96 → func2 param=0x96
// 05 5c → func5 param=0x5c

// 变换函数映射 (根据断点分析确认):
// func0: _0x509c46 - 检查参数，无变换
// func1: _0x5dd6b9 - XOR 固定值
// func2: _0x1d8917 - ADD 固定值
// func3: _0x5995f1 - XOR 递增 (param++)
// func4: _0x446610 - ADD 递增 (param++)
// func5: _0x20f9c7 - XOR 递减 (param--)
// func6: _0x23c1c7 - ADD 递减 (param--)

// func1: XOR 固定值
function transform1(block, param) {
    return block.map(b => toSignedByte(toUnsignedByte(b) ^ toUnsignedByte(param)));
}

// func2: ADD 固定值
function transform2(block, param) {
    return block.map(b => toSignedByte(b + param));
}

// func3: XOR 递增 (param++)
function transform3(block, param) {
    return block.map((b, i) => toSignedByte(toUnsignedByte(b) ^ toUnsignedByte(toSignedByte(param + i))));
}

// func4: ADD 递增 (param++)
function transform4(block, param) {
    return block.map((b, i) => toSignedByte(b + toSignedByte(param + i)));
}

// func5: XOR 递减 (param--)
function transform5(block, param) {
    return block.map((b, i) => toSignedByte(toUnsignedByte(b) ^ toUnsignedByte(toSignedByte(param - i))));
}

// func6: ADD 递减 (param--)
function transform6(block, param) {
    return block.map((b, i) => toSignedByte(b + toSignedByte(param - i)));
}

// 执行4层变换 (根据变换序列 "037606da0296055c")
function applyTransforms(block) {
    let result = block.slice();

    // 第1层: func3 param=0x76 (XOR递增)
    result = transform3(result, 0x76);

    // 第2层: func6 param=0xda (ADD递减)
    result = transform6(result, toSignedByte(0xda));

    // 第3层: func2 param=0x96 (ADD固定)
    result = transform2(result, toSignedByte(0x96));

    // 第4层: func5 param=0x5c (XOR递减)
    result = transform5(result, 0x5c);

    return result;
}

// ============ 数据填充 ============

// 填充数据到64字节块
function padData(data) {
    const len = data.length;
    // 计算需要的填充长度
    const padLen = len % 64 <= 60 ? 64 - len % 64 - 4 : 128 - len % 64 - 4;

    const result = data.slice();
    // 添加零填充
    for (let i = 0; i < padLen; i++) {
        result.push(0);
    }
    // 添加4字节长度 (大端序, 但实际只用最后1字节)
    result.push(0, 0, 0, len);

    return result;
}

// 分块 (每块64字节)
function splitBlocks(data) {
    const blocks = [];
    for (let i = 0; i < data.length; i += 64) {
        blocks.push(data.slice(i, i + 64));
    }
    return blocks;
}

// ============ 自定义 Base64 编码 ============

function customBase64Encode(bytes) {
    let result = '';
    const len = bytes.length;

    for (let i = 0; i < len; i += 3) {
        const b0 = toUnsignedByte(bytes[i]);
        const b1 = i + 1 < len ? toUnsignedByte(bytes[i + 1]) : 0;
        const b2 = i + 2 < len ? toUnsignedByte(bytes[i + 2]) : 0;

        const idx0 = b0 >> 2;
        const idx1 = ((b0 & 3) << 4) | (b1 >> 4);
        const idx2 = ((b1 & 15) << 2) | (b2 >> 6);
        const idx3 = b2 & 63;

        result += BASE64_CHARS[idx0];
        result += BASE64_CHARS[idx1];

        if (i + 1 < len) {
            result += BASE64_CHARS[idx2];
        } else {
            result += BASE64_PAD;
        }

        if (i + 2 < len) {
            result += BASE64_CHARS[idx3];
        } else {
            result += BASE64_PAD;
        }
    }

    return result;
}

// ============ 核心加密函数 ============

function encrypt(input) {
    // 1. 字符串转字节
    const inputBytes = stringToBytes(input);

    // 2. 计算CRC32
    const crcHex = crc32(inputBytes);
    const crcBytes = stringToBytes(crcHex);

    // 3. 合并数据
    const combined = inputBytes.concat(crcBytes);

    // 4. 填充到64字节块
    const padded = padData(combined);

    // 5. 分块
    const blocks = splitBlocks(padded);

    // 6. 生成密钥
    const [mainKey, iv] = generateMainKey();

    // 7. 初始化输出 (IV在前)
    const output = iv.slice();

    // 8. 链式密钥初始化为主密钥
    let chainKey = mainKey.slice();

    // 9. 分块加密
    for (let i = 0; i < blocks.length; i++) {
        const block = blocks[i];

        // Step 1: 4层变换
        let transformed = applyTransforms(block);

        // Step 2: XOR 主密钥
        transformed = xorArrays(transformed, mainKey);

        // Step 3: ADD 链式密钥
        transformed = addArrays(transformed, chainKey);

        // Step 4: XOR 链式密钥
        transformed = xorArrays(transformed, chainKey);

        // Step 5: 双重 S-Box
        transformed = doubleSbox(transformed);

        // 更新链式密钥
        chainKey = transformed.slice();

        // 添加到输出
        for (let j = 0; j < 64; j++) {
            output[4 + i * 64 + j] = transformed[j];
        }
    }

    // 10. Base64编码
    return customBase64Encode(output);
}

// ============ CB 生成入口 ============

function generateCb() {
    // 1. 生成32字符随机串
    let randomStr = randomString(32);

    // 2. 在指定位置替换为code字符
    const chars = randomStr.split('');
    for (let i = 0; i < CODE_POS.length; i++) {
        chars[CODE_POS[i]] = CODE.charAt(i);
    }
    randomStr = chars.join('');

    // 3. 加密
    const cb = encrypt(randomStr);

    return cb;
}

// ============ 导出 ============

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        generateCb,
        encrypt,
        customBase64Encode,
        stringToBytes,
        crc32,
        CODE,
        CODE_POS,
        SEED_KEY,
        BASE64_CHARS
    };
}

// ============ 测试 ============

if (typeof require !== 'undefined' && require.main === module) {
    console.log('=== CB 参数加密流程验证 ===\n');

    // 使用断点捕获的真实数据进行验证
    const testInput = 'ZvSEVkvvoifqnv4vw7fQRo2r1M4SNaq6';
    const expectedBlock = [90,118,83,69,86,107,118,118,111,105,102,113,110,118,52,118,119,55,102,81,82,111,50,114,49,77,52,83,78,97,113,54,56,53,99,100,57,55,97,56,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,40];
    const expectedStep1 = [-64,43,-61,-16,-64,44,34,33];  // 4层变换后前8字节
    const expectedStep5 = [66,98,-120,53,-69,-71,116,61];  // 双重SBox后前8字节

    // 使用固定IV进行测试: [93,-69,-66,29]
    const fixedIV = [93,-69,-66,29];
    const fixedMainKey = [59,-33,-120,124,105,-120,-33,120,111,-114,-40,42,105,-120,-121,37,63,-115,-113,126,109,-120,-35,37,110,-39,-37,46,106,-113,-118,36,59,-33,-120,124,105,-120,-33,120,111,-114,-40,42,105,-120,-121,37,63,-115,-113,126,109,-120,-35,37,110,-39,-37,46,106,-113,-118,36];

    console.log('1. 测试CRC32:');
    const inputBytes = stringToBytes(testInput);
    console.log('   输入字节 (前8):', JSON.stringify(inputBytes.slice(0, 8)));
    const crcHex = crc32(inputBytes);
    console.log('   CRC32结果:', crcHex);
    console.log('   期望: 85cd97a8');
    console.log('   CRC32正确:', crcHex === '85cd97a8');

    console.log('\n2. 测试填充:');
    const crcBytes = stringToBytes(crcHex);
    const combined = inputBytes.concat(crcBytes);
    const padded = padData(combined);
    console.log('   填充后长度:', padded.length);
    console.log('   填充后末尾8字节:', JSON.stringify(padded.slice(-8)));
    console.log('   期望末尾:', JSON.stringify(expectedBlock.slice(-8)));
    console.log('   填充正确:', JSON.stringify(padded) === JSON.stringify(expectedBlock));

    console.log('\n3. 测试4层变换:');
    const step1 = applyTransforms(padded);
    console.log('   变换后 (前8):', JSON.stringify(step1.slice(0, 8)));
    console.log('   期望 (前8):', JSON.stringify(expectedStep1));
    console.log('   变换正确:', JSON.stringify(step1.slice(0, 8)) === JSON.stringify(expectedStep1));

    console.log('\n4. 测试完整加密 (使用固定密钥):');
    // Step 2: XOR 主密钥
    let s2 = xorArrays(step1, fixedMainKey);
    console.log('   XOR主密钥 (前8):', JSON.stringify(s2.slice(0, 8)));

    // Step 3: ADD 链式密钥(=主密钥)
    let s3 = addArrays(s2, fixedMainKey);
    console.log('   ADD链式 (前8):', JSON.stringify(s3.slice(0, 8)));

    // Step 4: XOR 链式密钥
    let s4 = xorArrays(s3, fixedMainKey);
    console.log('   XOR链式 (前8):', JSON.stringify(s4.slice(0, 8)));

    // Step 5: 双重SBox
    let s5 = doubleSbox(s4);
    console.log('   双重SBox (前8):', JSON.stringify(s5.slice(0, 8)));
    console.log('   期望 (前8):', JSON.stringify(expectedStep5));
    console.log('   加密正确:', JSON.stringify(s5.slice(0, 8)) === JSON.stringify(expectedStep5));

    console.log('\n=== 生成CB测试 ===\n');
    for (let i = 0; i < 3; i++) {
        const cb = generateCb();
        console.log(`cb${i + 1}: ${cb}`);
        console.log(`长度: ${cb.length}`);
        console.log('');
    }
}
