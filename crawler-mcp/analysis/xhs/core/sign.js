/**
 * 小红书签名生成模块
 *
 * 使用方法:
 *   const { getSign } = require('./sign');
 *   const signature = getSign('/api/sns/web/v1/search/notes', { keyword: '测试' });
 */

const crypto = require('crypto');

// 加载环境补丁
require('./env');
// 加载签名核心代码
require('./code');

// ==================== 编码工具 ====================

const BASE64_CHARS = "ZmserbBoHQtNP+wOcza/LpngG8yJq42KWYj0DSfdikx3VT16IlUAFM97hECvuRX5";

function tripletToBase64(e) {
    return BASE64_CHARS[e >> 18 & 63] + BASE64_CHARS[e >> 12 & 63] + BASE64_CHARS[e >> 6 & 63] + BASE64_CHARS[63 & e];
}

function encodeChunk(e, start, end) {
    const result = [];
    for (let i = start; i < end; i += 3) {
        const n = (e[i] << 16 & 0xff0000) + (e[i + 1] << 8 & 65280) + (255 & e[i + 2]);
        result.push(tripletToBase64(n));
    }
    return result.join('');
}

function b64Encode(bytes) {
    const len = bytes.length;
    const remainder = len % 3;
    const chunks = [];

    for (let i = 0; i < len - remainder; i += 16383) {
        chunks.push(encodeChunk(bytes, i, Math.min(i + 16383, len - remainder)));
    }

    if (remainder === 1) {
        const b = bytes[len - 1];
        chunks.push(BASE64_CHARS[b >> 2] + BASE64_CHARS[b << 4 & 63] + '==');
    } else if (remainder === 2) {
        const b = (bytes[len - 2] << 8) + bytes[len - 1];
        chunks.push(BASE64_CHARS[b >> 10] + BASE64_CHARS[b >> 4 & 63] + BASE64_CHARS[b << 2 & 63] + '=');
    }

    return chunks.join('');
}

function encodeUtf8(str) {
    const encoded = encodeURIComponent(str);
    const bytes = [];
    for (let i = 0; i < encoded.length; i++) {
        if (encoded[i] === '%') {
            bytes.push(parseInt(encoded[i + 1] + encoded[i + 2], 16));
            i += 2;
        } else {
            bytes.push(encoded.charCodeAt(i));
        }
    }
    return bytes;
}

function md5(str) {
    return crypto.createHash('md5').update(str).digest('hex');
}

// ==================== 签名生成 ====================

/**
 * 生成小红书 X-s 签名
 * @param {string} apiPath - API 路径，如 '/api/sns/web/v1/search/notes'
 * @param {object} data - 请求体数据
 * @returns {string} X-s 签名
 */
function getSign(apiPath, data) {
    const payload = apiPath + JSON.stringify(data);
    const hash1 = md5(payload);
    const hash2 = md5(apiPath);

    const mnsSign = window.mnsv2(payload, hash1, hash2);

    const signData = {
        x0: "4.3.2",
        x1: "xhs-pc-web",
        x2: "Windows",
        x3: mnsSign,
        x4: "object"
    };

    return "XYS_" + b64Encode(encodeUtf8(JSON.stringify(signData)));
}

/**
 * 获取当前时间戳（毫秒）
 * @returns {string}
 */
function getTimestamp() {
    return String(Date.now());
}

// ==================== 导出 ====================

module.exports = {
    getSign,
    getTimestamp,
    md5
};

// 命令行调用支持
if (require.main === module) {
    const args = process.argv.slice(2);
    if (args.length >= 2) {
        // 两个参数：apiPath 和 data
        const apiPath = args[0];
        const data = JSON.parse(args[1]);
        console.log(getSign(apiPath, data));
    } else if (args.length === 1) {
        // 一个参数：只有 data，使用默认的搜索 API
        const data = JSON.parse(args[0]);
        const apiPath = '/api/sns/web/v1/search/notes';
        console.log(getSign(apiPath, data));
    } else {
        console.log('Usage: node sign.js [apiPath] <jsonData>');
    }
}
