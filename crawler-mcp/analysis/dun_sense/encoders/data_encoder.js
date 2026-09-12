/**
 * data 参数生成器 (m/p/ext)
 * 网易盾无感验证码逆向
 * 用于 /api/v3/check 接口
 */

// 引入 cb 加密函数
const cbEncoder = require('./cb_encoder.js');

// ============ 内层编码常量 (_0xc11b9d) ============

// 自定义 Base64 字符集 (64字符)
const INNER_BASE64_CHARS = [
    'i', '/', 'x', '1', 'X', 'g', 'U', '0', 'z', '7', 'k', '8', 'N', '+', 'l', 'C',
    'p', 'O', 'n', 'P', 'r', 'v', '6', '\\', 'q', 'u', '2', 'G', 'j', '9', 'H', 'R',
    'c', 'w', 'T', 'Y', 'Z', '4', 'b', 'f', 'S', 'J', 'B', 'h', 'a', 'W', 's', 't',
    'A', 'e', 'o', 'M', 'I', 'E', 'Q', '5', 'm', 'D', 'd', 'V', 'F', 'L', 'K', 'y'
];
const INNER_BASE64_PAD = '3';

// ============ 工具函数 ============

/**
 * 字符串转字节数组 (UTF-8)
 */
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
    return bytes;
}

/**
 * 转有符号字节
 */
function toSignedByte(val) {
    val = val & 0xFF;
    return val > 127 ? val - 256 : val;
}

/**
 * 转无符号字节
 */
function toUnsignedByte(val) {
    return ((val % 256) + 256) % 256;
}

/**
 * XOR 两个字节数组 (循环使用第二个数组)
 */
function xorArrays(data, key) {
    const result = [];
    const keyLen = key.length;
    for (let i = 0; i < data.length; i++) {
        result[i] = toSignedByte(data[i] ^ key[i % keyLen]);
    }
    return result;
}

/**
 * 内层 Base64 编码
 * 字符集: i/x1XgU0z7k8N+lCpOnPrv6\qu2Gj9HRcwTYZ4bfSJBhaWstAeoMIEQ5mDdVFLKy
 * 填充: 3
 */
function innerBase64Encode(bytes) {
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

        result += INNER_BASE64_CHARS[idx0];
        result += INNER_BASE64_CHARS[idx1];

        if (i + 1 < len) {
            result += INNER_BASE64_CHARS[idx2];
        } else {
            result += INNER_BASE64_PAD;
        }

        if (i + 2 < len) {
            result += INNER_BASE64_CHARS[idx3];
        } else {
            result += INNER_BASE64_PAD;
        }
    }

    return result;
}

// ============ 核心编码函数 ============

/**
 * 内层编码 _0xc11b9d
 * XOR(data, token) + 自定义 Base64
 *
 * @param {string} token - 验证码 token (32字符)
 * @param {string} data - 要编码的数据
 * @returns {string} 编码后的字符串
 */
function innerEncode(token, data) {
    const dataBytes = stringToBytes(data);
    const tokenBytes = stringToBytes(token);
    const xorResult = xorArrays(dataBytes, tokenBytes);
    return innerBase64Encode(xorResult);
}

/**
 * 外层加密 (复用 cb 加密函数)
 *
 * @param {string} input - 输入字符串
 * @returns {string} 92字符加密结果
 */
function outerEncrypt(input) {
    return cbEncoder.encrypt(input);
}

// ============ data 参数生成 ============

/**
 * 编码单个轨迹点
 *
 * @param {string} token - 验证码 token
 * @param {string} point - 轨迹点 "x,y,time"
 * @returns {string} 编码后的轨迹点
 */
function encodeTracePoint(token, point) {
    return innerEncode(token, point);
}

/**
 * 生成 data.m 参数
 *
 * @param {string} token - 验证码 token
 * @param {string[]} traceData - 原始轨迹数组 ["x,y,t", ...]
 * @param {number} maxSample - 最大采样数量，默认50
 * @returns {string} 加密后的 m 参数 (92字符)
 */
function generateDataM(token, traceData, maxSample = 50) {
    // 1. 每个轨迹点用 innerEncode 编码
    const encodedPoints = traceData.map(point => innerEncode(token, point));

    // 2. 采样（取前 maxSample 个）
    const sampled = encodedPoints.slice(0, maxSample);

    // 3. 用 ':' 连接
    const joined = sampled.join(':');

    // 4. 外层加密
    return outerEncrypt(joined);
}

/**
 * 生成 data.p 参数
 *
 * @param {string} token - 验证码 token
 * @param {number} clickX - 点击相对 X 坐标
 * @param {number} clickY - 点击相对 Y 坐标
 * @param {number} timeDelta - 从页面加载到点击的时间差(ms)
 * @param {boolean} isTrusted - 是否真实点击
 * @returns {string} 加密后的 p 参数 (92字符)
 */
function generateDataP(token, clickX, clickY, timeDelta, isTrusted = true) {
    // 1. 构建点击信息
    const clickInfo = `${Math.round(clickX)},${Math.round(clickY)},${timeDelta},${isTrusted ? 1 : 2}`;

    // 2. 内层编码
    const encoded = innerEncode(token, clickInfo);

    // 3. 外层加密
    return outerEncrypt(encoded);
}

/**
 * 生成 data.ext 参数
 *
 * @param {string} token - 验证码 token
 * @param {number} traceLength - 轨迹数组长度
 * @returns {string} 加密后的 ext 参数 (92字符)
 */
function generateDataExt(token, traceLength) {
    // 1. 构建 ext 信息
    const extInfo = `1,${traceLength}`;

    // 2. 内层编码
    const encoded = innerEncode(token, extInfo);

    // 3. 外层加密
    return outerEncrypt(encoded);
}

/**
 * 生成完整的 data 对象
 *
 * @param {string} token - 验证码 token
 * @param {string[]} traceData - 轨迹数组 ["x,y,t", ...]
 * @param {object} clickInfo - 点击信息 {x, y, timeDelta, isTrusted}
 * @returns {object} data 对象 {d, m, p, ext}
 */
function generateData(token, traceData, clickInfo) {
    return {
        d: '',  // 无感验证无拖动数据
        m: generateDataM(token, traceData),
        p: generateDataP(token, clickInfo.x, clickInfo.y, clickInfo.timeDelta, clickInfo.isTrusted),
        ext: generateDataExt(token, traceData.length)
    };
}

/**
 * 生成模拟的轨迹数据
 * 用于无感验证的简单场景
 *
 * @param {number} startX - 起始 X
 * @param {number} startY - 起始 Y
 * @param {number} endX - 结束 X
 * @param {number} endY - 结束 Y
 * @param {number} duration - 总时长(ms)
 * @returns {string[]} 轨迹数组
 */
function generateMockTrace(startX, startY, endX, endY, duration = 500) {
    const trace = [];
    const steps = 5 + Math.floor(Math.random() * 10);  // 5-15 个点

    for (let i = 0; i <= steps; i++) {
        const progress = i / steps;
        const x = Math.round(startX + (endX - startX) * progress + (Math.random() - 0.5) * 2);
        const y = Math.round(startY + (endY - startY) * progress + (Math.random() - 0.5) * 2);
        const t = Math.round(duration * progress);
        trace.push(`${x},${y},${t}`);
    }

    return trace;
}

// ============ 导出 ============

module.exports = {
    // 核心函数
    innerEncode,
    outerEncrypt,

    // data 参数生成
    generateDataM,
    generateDataP,
    generateDataExt,
    generateData,

    // 轨迹相关
    encodeTracePoint,
    generateMockTrace,

    // 工具函数
    stringToBytes,
    xorArrays,
    innerBase64Encode,

    // 常量
    INNER_BASE64_CHARS,
    INNER_BASE64_PAD
};

// ============ 测试 ============

if (require.main === module) {
    console.log('=== data 参数生成测试 ===\n');

    // 模拟 token
    const token = 'ff1fc2b52e004cc8b56653369633daae';

    // 测试内层编码
    console.log('1. 内层编码测试:');
    console.log('   innerEncode(token, "1,8"):', innerEncode(token, '1,8'));
    console.log('   innerEncode(token, "191,33,1"):', innerEncode(token, '191,33,1'));
    console.log('   innerEncode(token, "189,16,361,1"):', innerEncode(token, '189,16,361,1'));

    // 模拟轨迹数据
    const traceData = [
        '191,33,1',
        '190,27,8',
        '189,22,16',
        '189,20,24',
        '189,19,32',
        '189,17,40',
        '189,16,48',
        '189,16,305'
    ];

    console.log('\n2. 轨迹数据:');
    console.log('   原始:', traceData.slice(0, 3).join(', '), '...');
    console.log('   长度:', traceData.length);

    // 生成 data 参数
    const clickInfo = {
        x: 189,
        y: 16,
        timeDelta: 361,
        isTrusted: true
    };

    console.log('\n3. 生成 data 参数:');
    const data = generateData(token, traceData, clickInfo);
    console.log('   d:', data.d || '(空)');
    console.log('   m:', data.m.slice(0, 40) + '...');
    console.log('   m 长度:', data.m.length);
    console.log('   p:', data.p.slice(0, 40) + '...');
    console.log('   p 长度:', data.p.length);
    console.log('   ext:', data.ext.slice(0, 40) + '...');
    console.log('   ext 长度:', data.ext.length);

    // JSON 输出
    console.log('\n4. JSON 格式:');
    console.log(JSON.stringify(data, null, 2));
}
