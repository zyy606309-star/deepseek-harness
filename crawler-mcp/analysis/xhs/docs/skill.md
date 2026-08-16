# JavaScript 补环境技巧 (skill.md) v2.0

> ⚠️ **使用说明**
> - 本文档配合 **MCP 爬虫工具** 在真实浏览器的 **DevTools Console** 中使用
> - 以下代码均为 **示例模板**，实际会遇到各种不同的对象和实例
> - 核心是掌握 **定位方法**，举一反三应用到任意环境

---

## 一、补环境完整流程

```
1. 准备阶段
   ├── safeFunction 伪装（放最前面）
   ├── delete __filename / __dirname
   └── window = global; delete global
        ↓
2. 运行脚本 → Proxy 吐环境
   └── 监控 window、document、navigator、screen 等所有对象
        ↓
3. 找到 => undefined → 去浏览器 DevTools 验证
   ├── typeof xxx                    # 确认类型
   ├── xxx.hasOwnProperty('prop')    # 自身还是原型链
   └── 追溯完整原型链（到 Node 或 EventTarget）
        ↓
4. 补环境 + safeFunction 伪装
        ↓
5. 重复 2-4 直到签名成功
```

---

## 二、基础模板代码

### 2.1 safeFunction（必须放在最前面）

```javascript
!(function () {
    const $toString = Function.prototype.toString;
    const symbol = Symbol();
    const myToString = function () {
        return typeof this === 'function' && this[symbol] || $toString.call(this);
    }
    function safeFunction(func, key, value) {
        Object.defineProperty(func, key, {
            enumerable: false,
            configurable: true,
            writable: true,
            value: value,
        })
    };
    delete Function.prototype.toString;
    safeFunction(Function.prototype, "toString", myToString);
    safeFunction(Function.prototype.toString, symbol, 'function toString() { [native code] }');
    globalThis.safeFunction = function (func, funcname) {
        safeFunction(func, symbol, `function ${funcname || func.name || ''}() { [native code] }`);
    }
})();
```

### 2.2 隐藏 Node.js 特征

```javascript
delete __filename;
delete __dirname;
window = global;
delete global;
```

### 2.3 Proxy 监控函数（监控所有对象）

```javascript
function watch(obj, objName) {
    return new Proxy(obj, {
        get(target, prop) {
            const val = target[prop];
            console.log(`[GET] ${objName}.${String(prop)} => ${typeof val}`);
            return val;
        },
        set(target, prop, value) {
            console.log(`[SET] ${objName}.${String(prop)} = ${typeof value}`);
            target[prop] = value;
            return true;
        }
    });
}

// 把所有可能被访问的对象都加入监控
navigator = watch(navigator, 'navigator');
screen = watch(screen, 'screen');
document = watch(document, 'document');
window = watch(window, 'window');
```

---

## 三、浏览器验证方法

### 3.1 确认属性类型

```javascript
typeof document.cookie           // "string"
typeof document.addEventListener // "function"
typeof navigator.webdriver       // "boolean"
```

### 3.2 定位属性位置（hasOwnProperty）

```javascript
// 不断往上找，直到找到 true
document.hasOwnProperty('cookie')                    // false
document.__proto__.hasOwnProperty('cookie')          // false
document.__proto__.__proto__.hasOwnProperty('cookie') // true ✅ → Document.prototype
```

### 3.3 查看完整原型链

```javascript
let obj = document.documentElement;
let chain = [];
while(obj) {
    chain.push(obj.constructor.name);
    obj = obj.__proto__;
}
chain
// ["HTMLHtmlElement", "HTMLHtmlElement", "HTMLElement", "Element", "Node", "EventTarget", "Object"]
```

### 3.4 获取属性描述符

```javascript
Object.getOwnPropertyDescriptor(Document.prototype, 'cookie')
// {get: ƒ, set: ƒ, enumerable: true, configurable: true}
```

---

## 四、核心原型链结构

### 4.1 DOM 对象原型链图

```
                         EventTarget
                        /           \
                     Node            Window
                   /     \              |
              Document   Element      window
                 |          |
           HTMLDocument  HTMLElement
                 |        /    \
             document   HTMLHtmlElement  HTMLBodyElement
                              |              |
                       documentElement      body
```

### 4.2 document 原型链（补到 EventTarget）

```javascript
function EventTarget() {}
safeFunction(EventTarget);
EventTarget.prototype.addEventListener = function addEventListener() {};
safeFunction(EventTarget.prototype.addEventListener);

function Node() {}
safeFunction(Node);
Object.setPrototypeOf(Node.prototype, EventTarget.prototype);

function Document() {}
safeFunction(Document);
Object.setPrototypeOf(Document.prototype, Node.prototype);

function HTMLDocument() {}
safeFunction(HTMLDocument);
Object.setPrototypeOf(HTMLDocument.prototype, Document.prototype);

document = new HTMLDocument();
window.document = document;
```

### 4.3 Element 原型链（补到 Node）

```javascript
function Element() { Node.call(this); }
safeFunction(Element);
Object.setPrototypeOf(Element.prototype, Node.prototype);
Element.prototype.getAttribute = function getAttribute() {};
safeFunction(Element.prototype.getAttribute);

function HTMLElement() { Element.call(this); }
safeFunction(HTMLElement);
Object.setPrototypeOf(HTMLElement.prototype, Element.prototype);
window.HTMLElement = HTMLElement;

function HTMLHtmlElement() { HTMLElement.call(this); }
safeFunction(HTMLHtmlElement);
Object.setPrototypeOf(HTMLHtmlElement.prototype, HTMLElement.prototype);

function HTMLBodyElement() { HTMLElement.call(this); }
safeFunction(HTMLBodyElement);
Object.setPrototypeOf(HTMLBodyElement.prototype, HTMLElement.prototype);

Document.prototype.documentElement = new HTMLHtmlElement();
Document.prototype.body = new HTMLBodyElement();
```

### 4.4 window 原型链

```javascript
function Window() {}
safeFunction(Window);
Object.setPrototypeOf(window, Window.prototype);

window.window = window;
window.top = window;
window.self = window;
```

### 4.5 navigator 原型链

```javascript
function Navigator() {}
safeFunction(Navigator);
Navigator.prototype.webdriver = false;
Navigator.prototype.userAgent = "";

// permissions
function PermissionStatus() {
    this.state = "denied";
    this.then = function then() {};
}
safeFunction(PermissionStatus);

function Permissions() {}
Permissions.prototype.query = function query() {
    return Promise.resolve(new PermissionStatus());
};
safeFunction(Permissions.prototype.query);
Navigator.prototype.permissions = new Permissions();

navigator = new Navigator();
window.navigator = navigator;
window.Navigator = Navigator;
```

---

## 五、补环境规则

### 5.1 补方法

```javascript
// 方法返回空数组/空对象即可
Document.prototype.getElementsByTagName = function getElementsByTagName() {
    return [];
};
safeFunction(Document.prototype.getElementsByTagName);
```

### 5.2 补属性

```javascript
Document.prototype.cookie = '';
Navigator.prototype.webdriver = false;
```

### 5.3 补构造函数

```javascript
function Screen() {}
safeFunction(Screen);
window.Screen = Screen;
screen = new Screen();
window.screen = screen;
```

---

## 六、调试技巧

### 6.1 过滤 Proxy 输出

```powershell
# 只看 undefined
node ceshi.js 2>&1 | Select-String "=> undefined"

# 只看特定对象
node ceshi.js 2>&1 | Select-String "navigator"
```

### 6.2 Node.js 调试模式

```bash
node --inspect-brk ceshi.js
# 然后 Chrome 打开 chrome://inspect
```

---

## 七、MCP 工具配合

```javascript
// 启动真实浏览器
await launch_real_chrome()
await connect_existing_tab()

// 验证类型
await execute_js({ code: "typeof document.cookie" })

// 验证原型链
await execute_js({ code: "Document.prototype.hasOwnProperty('cookie')" })

// 获取完整原型链
await execute_js({
    code: `let el = document; let chain = [];
           while(el) { chain.push(el.constructor.name); el = el.__proto__; }
           chain`
})
```

---

## 八、核心原则

1. **原型链补完整** - DOM 对象补到 Node 或 EventTarget
2. **safeFunction 必加** - 所有函数都要伪装 toString
3. **监控要全面** - navigator、screen、document 都要 watch
4. **去浏览器验证** - 不要猜，用 MCP 去真实浏览器查
5. **迭代调试** - 补一个测一个，不要一次补太多
