# 📱 APP 抓包绕过 SSL Pinning

> 使用 Frida 绕过 Android 应用的 SSL 证书锁定，实现 HTTPS 抓包

## 使用边界

本文是自研或已授权测试包的诊断笔记。优先使用测试构建、调试开关、Network Security Config 或应用自带日志；动态修改只用于确认验证发生在哪里，不把永久绕过脚本当成生产修复。

---

## 一、核心概念

### SSL Pinning 是什么？

应用在代码中**硬编码**了服务器证书/公钥指纹，即使中间人代理证书被系统信任，也会因指纹不匹配而拒绝连接。

### Pin 的三种对象

| 对象 | 说明 | 安全性 |
|-----|------|-------|
| 整个证书 | 比对完整 DER 编码 | 最严格 |
| 公钥 (SPKI) | 比对 SubjectPublicKeyInfo | 推荐 |
| 公钥哈希 | SHA-256 哈希 | 最常用 |

---

## 二、环境准备

### 2.1 安装 Frida

```bash
pip install frida-tools
```

### 2.2 部署 frida-server

```bash
# 下载对应架构版本
# https://github.com/frida/frida/releases

# 推送到设备
adb push frida-server /data/local/tmp/
adb shell chmod +x /data/local/tmp/frida-server

# 启动（需要 root）
adb shell
su
/data/local/tmp/frida-server &
```

### 2.3 配置代理

```bash
# 方式1：WiFi 代理设置
# 方式2：iptables 透明代理（仅限隔离测试设备；记录原规则并在结束后删除）
adb shell iptables -t nat -A OUTPUT -p tcp --dport 443 -j DNAT --to-destination 192.168.1.100:8888
```

不要把宿主机地址、端口和规则当成通用模板。先确认设备路由、代理监听地址、目标 UID/进程范围，并保存对应回滚命令。

### 2.4 安装 CA 证书

Android 7.0+ 需要安装到**系统信任存储**：

```bash
# 转换证书格式
openssl x509 -inform DER -in burp.der -out burp.pem
HASH=$(openssl x509 -inform PEM -subject_hash_old -in burp.pem | head -1)
mv burp.pem $HASH.0

# 安装到系统目录（需要 root）
adb push $HASH.0 /system/etc/security/cacerts/
adb shell chmod 644 /system/etc/security/cacerts/$HASH.0
```

---

## 三、9 种绕过方案

### 方案 1：通用脚本（优先尝试）

通用 unpinning 只能作为定位手段。命中脚本不等于已经覆盖目标连接栈；必须记录命中的类/函数、请求是否真正经过代理、证书链和应用层响应。

#### objection
```bash
pip install objection
objection -g com.example.app explore
# 进入后执行
android sslpinning disable
```

#### frida-multiple-unpinning
```bash
# 下载: https://github.com/AeonLucid/frida-android-unpinning-scripts
frida -U -f com.example.app -l unpinning.js
```

#### 全局 TrustManager 替换
```javascript
Java.perform(function() {
    var TrustManager = Java.registerClass({
        name: 'com.bypass.TrustManager',
        implements: [Java.use('javax.net.ssl.X509TrustManager')],
        methods: {
            checkClientTrusted: function(chain, authType) {},
            checkServerTrusted: function(chain, authType) {},
            getAcceptedIssuers: function() { return []; }
        }
    });

    var SSLContext = Java.use('javax.net.ssl.SSLContext');
    SSLContext.init.overload(
        '[Ljavax.net.ssl.KeyManager;',
        '[Ljavax.net.ssl.TrustManager;',
        'java.security.SecureRandom'
    ).implementation = function(km, tm, sr) {
        this.init(km, [TrustManager.$new()], sr);
    };
});
```

---

### 方案 2：Network Security Configuration

**特征**：`res/xml/network_security_config.xml` 中配置 `<pin-set>`

```javascript
Java.perform(function() {
    var NetworkSecurityTrustManager = Java.use('android.security.net.config.NetworkSecurityTrustManager');
    NetworkSecurityTrustManager.checkServerTrusted.implementation = function(chain, authType) {
        console.log('[*] Bypassing NetworkSecurityTrustManager');
    };
});
```

---

### 方案 3：OkHttp CertificatePinner

**特征**：使用 `okhttp3.CertificatePinner`

```javascript
Java.perform(function() {
    // 标准包名
    try {
        var CertificatePinner = Java.use('okhttp3.CertificatePinner');
        CertificatePinner.check.overload('java.lang.String', 'java.util.List').implementation = function(hostname, peerCertificates) {
            console.log('[*] OkHttp3 bypass: ' + hostname);
        };
    } catch(e) {}

    // 混淆情况：搜索 "sha256/" 字符串定位
});
```

---

### 方案 4：自定义 TrustManager

```javascript
Java.perform(function() {
    var X509TrustManager = Java.use('javax.net.ssl.X509TrustManager');
    var SSLContext = Java.use('javax.net.ssl.SSLContext');

    // 枚举所有实现类
    Java.enumerateLoadedClasses({
        onMatch: function(className) {
            try {
                var clazz = Java.use(className);
                if (clazz.$intf && clazz.$intf.includes('javax.net.ssl.X509TrustManager')) {
                    clazz.checkServerTrusted.implementation = function() {
                        console.log('[*] Bypassing: ' + className);
                    };
                }
            } catch(e) {}
        },
        onComplete: function() {}
    });
});
```

---

### 方案 5：自定义 HostnameVerifier

```javascript
Java.perform(function() {
    var HostnameVerifier = Java.use('javax.net.ssl.HostnameVerifier');

    Java.enumerateLoadedClasses({
        onMatch: function(className) {
            try {
                var clazz = Java.use(className);
                if (clazz.verify) {
                    clazz.verify.overload('java.lang.String', 'javax.net.ssl.SSLSession')
                        .implementation = function(hostname, session) {
                        console.log('[*] HostnameVerifier bypass: ' + hostname);
                        return true;
                    };
                }
            } catch(e) {}
        },
        onComplete: function() {}
    });
});
```

---

### 方案 6：嵌入证书文件 (KeyStore)

**特征**：assets 目录存在 `.cer`、`.bks`、`.p12` 文件

```javascript
Java.perform(function() {
    var TrustManagerFactory = Java.use('javax.net.ssl.TrustManagerFactory');
    TrustManagerFactory.init.overload('java.security.KeyStore').implementation = function(keyStore) {
        console.log('[*] Bypassing embedded KeyStore');
        this.init(null);  // 使用系统默认信任存储
    };
});
```

---

### 方案 7：第三方库

#### TrustKit
```javascript
Java.perform(function() {
    var PinningTrustManager = Java.use('com.datatheorem.android.trustkit.pinning.PinningTrustManager');
    PinningTrustManager.checkServerTrusted.implementation = function() {
        console.log('[*] TrustKit bypass');
    };
});
```

#### Conscrypt
```javascript
Java.perform(function() {
    var TrustManagerImpl = Java.use('com.android.org.conscrypt.TrustManagerImpl');
    TrustManagerImpl.verifyChain.implementation = function() {
        console.log('[*] Conscrypt bypass');
        return arguments[0];
    };
});
```

---

### 方案 8：WebView SSL Pinning

```javascript
Java.perform(function() {
    var WebViewClient = Java.use('android.webkit.WebViewClient');
WebViewClient.onReceivedSslError.implementation = function(view, handler, error) {
    console.log('[*] WebView SSL bypass');
    // 仅用于测试构建；生产代码应按 error 类型 fail closed。
    handler.proceed();
};
});
```

---

### 方案 9：Native 层 SSL Pinning

#### libssl.so / libboringssl.so
```javascript
Interceptor.attach(Module.findExportByName('libssl.so', 'SSL_CTX_set_verify'), {
    onEnter: function(args) {
        args[1] = ptr(0);  // 禁用验证
    }
});

Interceptor.attach(Module.findExportByName('libssl.so', 'SSL_get_verify_result'), {
    onLeave: function(retval) {
        retval.replace(0);  // 返回验证成功
    }
});
```

Native 返回值强改必须先确认 ABI、库版本、调用约定和返回值语义；`retval.replace(0)` 不是通用成功标志，错误 hook 可能导致崩溃或掩盖真正的 TLS 失败原因。

#### 字节跳动 libttboringssl.so
```javascript
// 监听 dlopen 加载
Interceptor.attach(Module.findExportByName(null, 'dlopen'), {
    onEnter: function(args) {
        this.lib = args[0].readUtf8String();
    },
    onLeave: function(retval) {
        if (this.lib && this.lib.includes('ttboringssl')) {
            hookTTBoringSSL();
        }
    }
});

function hookTTBoringSSL() {
    var exports = Module.enumerateExports('libttboringssl.so');
    exports.forEach(function(exp) {
        if (exp.name.includes('verify')) {
            Interceptor.attach(exp.address, {
                onLeave: function(retval) {
                    retval.replace(1);
                }
            });
        }
    });
}
```

#### libcurl.so
```javascript
Interceptor.attach(Module.findExportByName('libcurl.so', 'curl_easy_setopt'), {
    onEnter: function(args) {
        var option = args[1].toInt32();
        // CURLOPT_SSL_VERIFYPEER = 64
        // CURLOPT_SSL_VERIFYHOST = 81
        if (option === 64 || option === 81) {
            args[2] = ptr(0);
        }
    }
});
```

---

## 四、mTLS 双向认证绕过

### 提取客户端证书

```javascript
Java.perform(function() {
    var KeyStore = Java.use('java.security.KeyStore');

    KeyStore.load.overload('java.io.InputStream', '[C').implementation = function(stream, password) {
        console.log('[*] KeyStore password: ' + (password ? Java.use('java.lang.String').$new(password) : 'null'));
        this.load(stream, password);
    };
});
```

### 导出证书

```javascript
Java.perform(function() {
    var KeyStore = Java.use('java.security.KeyStore');
    var FileOutputStream = Java.use('java.io.FileOutputStream');

    KeyStore.load.overload('java.io.InputStream', '[C').implementation = function(stream, password) {
        this.load(stream, password);

        // 导出为 PKCS12
        var fos = FileOutputStream.$new('/data/local/tmp/client.p12');
        this.store(fos, password);
        fos.close();
        console.log('[*] Exported to /data/local/tmp/client.p12');
    };
});
```

### 导入 Burp Suite

```bash
adb pull /data/local/tmp/client.p12
# Burp -> User options -> TLS -> Client TLS Certificates -> Add
```

---

## 五、高级对抗

### 5.1 代码被混淆

通过异常追溯：
```javascript
Java.perform(function() {
    var CertificateException = Java.use('java.security.cert.CertificateException');
    CertificateException.$init.overload('java.lang.String').implementation = function(msg) {
        console.log('[*] CertificateException: ' + msg);
        console.log(Java.use('android.util.Log').getStackTraceString(Java.use('java.lang.Exception').$new()));
        return this.$init(msg);
    };
});
```

### 5.2 Frida 检测绕过

```bash
# 非默认端口
./frida-server -l 0.0.0.0:31337 &
frida -H 192.168.1.2:31337 -f com.example.app -l bypass.js

# 重命名
mv frida-server fs-daemon

# 使用 Frida Gadget
# 将 libfrida-gadget.so 注入 APK
```

这里应记录检测证据和测试包配置，不要把改名、远程端口或注入步骤写成默认生产方案。测试结束后停止 frida-server、撤销代理并还原证书/iptables 状态。

---

## 六、难度速查表

| 场景 | 推荐方案 | 难度 |
|-----|---------|-----|
| 常规应用 | objection / 通用脚本做初筛 | ⭐ |
| OkHttp | 方案3 | ⭐⭐ |
| 自定义 TrustManager | 方案4 枚举 | ⭐⭐ |
| Network Security Config | 方案2 | ⭐⭐ |
| 嵌入证书 | 方案6 | ⭐⭐ |
| Native SSL | 方案9 | ⭐⭐⭐⭐ |
| 字节系应用 | ttboringssl | ⭐⭐⭐⭐⭐ |
| Frida 检测 + 混淆 | 多方案组合 | ⭐⭐⭐⭐⭐ |

---

## 七、常用工具

每次记录：应用版本、Android 版本、ABI、连接库、命中的验证点、代理是否收到握手、回滚动作和最终请求结果。没有这些信息，脚本成功也无法判断是否可迁移。

| 工具 | 用途 |
|-----|------|
| **Frida** | 动态 Hook |
| **objection** | Frida 封装，用于快速定位常见验证点 |
| **Burp Suite** | 代理抓包 |
| **Charles** | 代理抓包 |
| **apktool** | APK 反编译 |
| **jadx** | DEX 反编译为 Java |
