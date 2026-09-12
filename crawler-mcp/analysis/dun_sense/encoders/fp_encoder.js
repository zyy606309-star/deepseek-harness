/**
 * fp parameter encoder for Netease Dun captcha
 * Reverse engineered from core-optimi.min.js
 */

// Custom Base64 alphabet for fp
var FP_BASE64_CHARS = '240aYHiQxL\\ZufVlg8sPMR6dGkXvO/Cbw9WDj1ETyIScmeoJz37qthBrU+KNA5pn';
var FP_PAD_CHAR = 'F';
var BLOCK_LEN = 64;
var KEY_LEN = 4;

// S-Box lookup table (256 bytes)
var SBOX = [
    -9,-84,-50,59,115,102,57,125,94,-15,15,2,-72,-98,-79,38,
    -56,-49,76,-26,-117,60,90,9,-107,-12,-71,-100,63,42,-18,28,
    -120,-11,33,45,79,92,37,97,4,58,98,84,-97,-88,95,-104,
    -13,-89,78,-90,119,-66,13,-5,29,-116,-4,-81,27,40,-59,-43,
    85,48,-74,109,-64,26,67,-33,-115,0,-37,-102,88,-48,127,-86,
    41,105,-2,122,-42,112,-94,81,-31,-65,-101,-14,65,49,-67,-114,
    -103,-87,-19,104,66,-73,-34,-78,-45,-27,-109,-108,47,61,86,43,
    -54,25,64,-35,-44,53,-112,36,73,89,-82,51,-32,39,-83,80,
    -85,-111,12,-58,103,-76,-46,-127,34,1,-99,14,-57,110,106,93,
    -52,11,113,20,-106,75,62,-69,-39,-55,-119,126,114,123,10,77,
    -121,-8,74,21,-93,17,-61,-21,-105,-126,18,124,-17,52,-10,-77,
    -24,-22,120,-95,-25,96,-110,22,-23,69,-125,-128,-47,-38,-1,3,
    -20,100,68,101,5,117,-122,44,-51,-36,-41,24,-80,30,82,-63,
    -40,-92,91,-6,-53,-124,-62,-28,111,19,50,108,70,-68,-29,-75,
    99,-91,-60,-70,71,-118,-3,83,87,-7,32,55,31,-123,121,107,
    -113,46,-30,118,54,23,116,-16,7,6,35,16,-96,56,72,8
];

// CRC32 table
var CRC_TABLE = [
    0,1996959894,3993919788,2567524794,124634137,1886057615,3915621685,2657392035,
    249268274,2044508324,3772115230,2547177864,162941995,2125561021,3887607047,2428444049,
    498536548,1789927666,4089016648,2227061214,450548861,1843258603,4107580753,2211677639,
    325883990,1684777152,4251122042,2321926636,335633487,1661365465,4195302755,2366115317,
    997073096,1281953886,3579855332,2724688242,1006888145,1258607687,3524101629,2768942443,
    901097722,1119000684,3686517206,2898065728,853044451,1172266101,3705015759,2882616665,
    651767980,1373503546,3369554304,3218104598,565507253,1454621731,3485111705,3099436303,
    671266974,1594198024,3322730930,2970347812,795835527,1483230225,3244367275,3060149565,
    1994146192,31158534,2563907772,4023717930,1907459465,112637215,2680153253,3904427059,
    2013776290,251722036,2517215374,3775830040,2137656763,141376813,2439277719,3865271297,
    1802195444,476864866,2238001368,4066508878,1812370925,453092731,2181625025,4111451223,
    1706088902,314042704,2344532202,4240017532,1658658271,366619977,2362670323,4224994405,
    1303535960,984961486,2747007092,3569037538,1256170817,1037604311,2765210733,3554079995,
    1131014506,879679996,2909243462,3663771856,1141124467,855842277,2852801631,3708648649,
    1342533948,654459306,3188396048,3373015174,1466479909,544179635,3110523913,3462522015,
    1591671054,702138776,2966460450,3352799412,1504918807,783551873,3082640443,3233442989,
    3988292384,2596254646,62317068,1957810842,3939845945,2647816111,81470997,1943803523,
    3814918930,2489596804,225274430,2053790376,3826175755,2466906013,167816743,2097651377,
    4027552580,2265490386,503444072,1762050814,4150417245,2154129355,426522225,1852507879,
    4275313526,2312317920,282753626,1742555852,4189708143,2394877945,397917763,1622183637,
    3604390888,2714866558,953729732,1340076626,3518719985,2797360999,1068828381,1219638859,
    3624741850,2936675148,906185462,1090812512,3747672003,2825379669,829329135,1181335161,
    3412177804,3160834842,628085408,1382605366,3423369109,3138078467,570562233,1426400815,
    3317316542,2998733608,733239954,1555261956,3268935591,3050360625,752459403,1541320221,
    2607071920,3965973030,1969922972,40735498,2617837225,3943577151,1913087877,83908371,
    2512341634,3803740692,2075208622,213261112,2463272603,3855990285,2094854071,198958881,
    2262029012,4057260610,1759359992,534414190,2176718541,4139329115,1873836001,414664567,
    2282248934,4279200368,1711684554,285281116,2405801727,4167216745,1634467795,376229701,
    2685067896,3608007406,1308918612,956543938,2808555105,3495958263,1231636301,1047427035,
    2932959818,3654703836,1088359270,936918000,2847714899,3736837829,1202900863,817233897,
    3183342108,3401237130,1404277552,615818150,3134207493,3453421203,1423857449,601450431,
    3009837614,3294710456,1567103746,711928724,3020668471,3272380065,1510334235,755167117
];

// Random chars for key generation
var RANDOM_CHARS = 'aZbY0cXdW1eVf2Ug3Th4SiR5jQk6PlO7mNn8MoL9pKqJrIsHtGuFvEwDxCyBzA';

function toSignedByte(val) {
    val = val & 0xff;
    return val > 127 ? val - 256 : val;
}

function xorBytes(a, b) {
    return toSignedByte(toSignedByte(a) ^ toSignedByte(b));
}

function stringToBytes(str) {
    var bytes = [];
    for (var i = 0; i < str.length; i++) {
        bytes.push(str.charCodeAt(i) & 0xff);
    }
    return bytes;
}

function generateKey(len) {
    var key = [];
    for (var i = 0; i < len; i++) {
        key.push(Math.floor(Math.random() * 256) - 128);
    }
    return key;
}

function crc32(bytes) {
    var crc = 0xFFFFFFFF;
    for (var i = 0; i < bytes.length; i++) {
        var b = bytes[i] & 0xff;
        crc = CRC_TABLE[(crc ^ b) & 0xff] ^ (crc >>> 8);
    }
    crc = (crc ^ 0xFFFFFFFF) >>> 0;
    return crc.toString(16).padStart(8, '0');
}

function padToBlockLen(data, blockLen) {
    var result = data.slice();
    while (result.length < blockLen) {
        result.push(0);
    }
    return result;
}

function sboxLookup(val) {
    return SBOX[val & 0xff];
}

function doubleSbox(bytes) {
    var result = [];
    for (var i = 0; i < bytes.length; i++) {
        var v = bytes[i] < 0 ? bytes[i] + 256 : bytes[i];
        var s1 = sboxLookup(v);
        var s2 = sboxLookup(s1 < 0 ? s1 + 256 : s1);
        result.push(s2);
    }
    return result;
}

function encryptBlock(block, key, prevBlock) {
    var result = block.slice();

    // Step 1: XOR 37
    for (var i = 0; i < BLOCK_LEN; i++) {
        result[i] = toSignedByte(result[i] ^ 37);
    }

    // Step 2: XOR decreasing (from 35)
    for (var i = 0; i < BLOCK_LEN; i++) {
        result[i] = toSignedByte(result[i] ^ (35 - i));
    }

    // Step 3: Add increasing (from -44)
    for (var i = 0; i < BLOCK_LEN; i++) {
        result[i] = toSignedByte(result[i] + (-44 + i));
    }

    // Step 4: XOR extended key
    for (var i = 0; i < BLOCK_LEN; i++) {
        result[i] = toSignedByte(result[i] ^ key[i % KEY_LEN]);
    }

    // Step 5 & 6: Add and XOR prev block
    if (prevBlock) {
        for (var i = 0; i < BLOCK_LEN; i++) {
            result[i] = toSignedByte(result[i] + prevBlock[i]);
        }
        for (var i = 0; i < BLOCK_LEN; i++) {
            result[i] = xorBytes(result[i], prevBlock[i]);
        }
    }

    // Step 7: Double S-Box
    result = doubleSbox(result);

    return result;
}

function fpBase64Encode(data) {
    var result = '';
    var chars = FP_BASE64_CHARS;

    for (var i = 0; i < data.length; i += 3) {
        var b0 = data[i] < 0 ? data[i] + 256 : data[i];
        var b1 = i + 1 < data.length ? (data[i+1] < 0 ? data[i+1] + 256 : data[i+1]) : 0;
        var b2 = i + 2 < data.length ? (data[i+2] < 0 ? data[i+2] + 256 : data[i+2]) : 0;

        result += chars[(b0 >>> 2) & 63];
        result += chars[((b0 << 4) & 48) | ((b1 >>> 4) & 15)];

        if (i + 1 < data.length) {
            result += chars[((b1 << 2) & 60) | ((b2 >>> 6) & 3)];
        } else {
            result += FP_PAD_CHAR;
        }

        if (i + 2 < data.length) {
            result += chars[b2 & 63];
        } else {
            result += FP_PAD_CHAR;
        }
    }

    return result;
}

function generateFpParam(options) {
    options = options || {};
    var host = options.host || 'dun.163.com';

    // Build fingerprint JSON (single quotes)
    var fpObj = {
        v: '2.28.5',
        fp: '',
        u: host,
        h: ''
    };

    // Serialize with single quotes
    var jsonStr = "{'v':'" + fpObj.v + "','fp':'" + fpObj.fp + "','u':'" + fpObj.u + "','h':'" + fpObj.h + "'}";
    var inputBytes = stringToBytes(jsonStr);

    // Calculate CRC32
    var crcHex = crc32(inputBytes);
    var crcBytes = stringToBytes(crcHex);

    // Combine and pad
    var combined = inputBytes.concat(crcBytes);

    // Pad to 128 bytes (2 blocks)
    while (combined.length < 128) {
        combined.push(0);
    }

    // Generate 4-byte key
    var key = generateKey(KEY_LEN);

    // Encrypt two blocks
    var block1 = combined.slice(0, BLOCK_LEN);
    var block2 = combined.slice(BLOCK_LEN, BLOCK_LEN * 2);

    var encrypted1 = encryptBlock(block1, key, null);
    var encrypted2 = encryptBlock(block2, key, encrypted1);

    // Assemble: key(4) + encrypted1(64) + encrypted2(64) = 132 bytes
    var result = key.concat(encrypted1).concat(encrypted2);

    // Base64 encode
    var encoded = fpBase64Encode(result);

    // Add timestamp
    return encoded + ':' + Date.now();
}

// Export
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        generateFpParam: generateFpParam,
        fpBase64Encode: fpBase64Encode,
        encryptBlock: encryptBlock,
        crc32: crc32
    };
}

// Test
if (typeof require !== 'undefined' && require.main === module) {
    var fp = generateFpParam({host: 'dun.163.com'});
    console.log('fp:', fp);
    console.log('length:', fp.split(':')[0].length);
}
