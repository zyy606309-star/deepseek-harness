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

// 1. 隐藏 Node.js 特征
delete __filename;
delete __dirname;

// 2. 基础 window 设置
window = global;
delete global;
window.window = window.top = window.self = window
// function Window() {
// }
// Object.setPrototypeOf(window, Window.prototype)
// 3. Proxy 监控函数
// function watch(obj, objName) {
//     return new Proxy(obj, {
//         get(target, prop) {
//             const val = target[prop];
//             const type = typeof val;
//             console.log(`[GET] ${objName}.${String(prop)} => ${type}`);
//             return val;
//         },
//         set(target, prop, value) {
//             console.log(`[SET] ${objName}.${String(prop)} = ${typeof value}`);
//             target[prop] = value;
//             return true;
//         }
//     });
// }

// ==================== 开始补环境 ====================

// 【第1轮】吐出: window.document => undefined
// 【第2轮】吐出: document.addEventListener => undefined
// 验证结果: 原型链 HTMLDocument → Document → Node → EventTarget
// addEventListener 在 EventTarget.prototype 上

// 构建原型链
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

// 【第6轮】吐出: document.documentElement => undefined
// 验证结果: object, Document.prototype 上的 getter, 返回 HTMLHtmlElement
// 完整原型链: HTMLHtmlElement → HTMLElement → Element → Node → EventTarget

// Element 继承 Node
function Element() {
    Node.call(this);
}
safeFunction(Element);
Object.setPrototypeOf(Element.prototype, Node.prototype);
Element.prototype.constructor = Element;
Element.prototype.getAttribute = function getAttribute() {};
safeFunction(Element.prototype.getAttribute);
Element.prototype.removeChild = function removeChild() {};
safeFunction(Element.prototype.removeChild);

// HTMLElement 继承 Element
function HTMLElement() {
    Element.call(this);
}
safeFunction(HTMLElement);
Object.setPrototypeOf(HTMLElement.prototype, Element.prototype);
HTMLElement.prototype.constructor = HTMLElement;
window.HTMLElement = HTMLElement;

// HTMLHtmlElement 继承 HTMLElement
function HTMLHtmlElement() {
    HTMLElement.call(this);
}
safeFunction(HTMLHtmlElement);
Object.setPrototypeOf(HTMLHtmlElement.prototype, HTMLElement.prototype);
HTMLHtmlElement.prototype.constructor = HTMLHtmlElement;

Document.prototype.documentElement = new HTMLHtmlElement();

// 【补充】document.getElementsByTagName
Document.prototype.getElementsByTagName = function getElementsByTagName(tagName) {
    return [];
};
safeFunction(Document.prototype.getElementsByTagName);

// 【补充】document.body (HTMLBodyElement 继承 HTMLElement)
function HTMLBodyElement() {
    HTMLElement.call(this);
}
safeFunction(HTMLBodyElement);
Object.setPrototypeOf(HTMLBodyElement.prototype, HTMLElement.prototype);
HTMLBodyElement.prototype.constructor = HTMLBodyElement;
Document.prototype.body = new HTMLBodyElement();

// 【补充】document.all
function HTMLAllCollection() {
    this.length = 0;
}
safeFunction(HTMLAllCollection);
Document.prototype.all = new HTMLAllCollection();

// 【第7轮】吐出: document.cookie => undefined
// 验证结果: string, Document.prototype 上
Document.prototype.cookie = '';

document = new HTMLDocument();
window.document = document;

// 【第3轮】吐出: window.Screen => undefined
// 验证结果: function, window 自身属性
function Screen() {}
safeFunction(Screen);
window.Screen = Screen;

// 【第4轮】吐出: window.MouseEvent => undefined
// 验证结果: function, window 自身属性
function MouseEvent() {}
safeFunction(MouseEvent);
window.MouseEvent = MouseEvent;

// 【第5轮】吐出: window.Navigator => undefined
// 验证结果: function, window 自身属性
function Navigator() {}
safeFunction(Navigator);

// 【第8轮】吐出: navigator.webdriver => undefined
// 验证结果: boolean, Navigator.prototype 上, 值为 false
Navigator.prototype.webdriver = false;

// 【补充】navigator 更多属性
Navigator.prototype.userAgent = "";
Navigator.prototype.userAgentData = undefined;

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

// 【补充】screen 实例
screen = new Screen();
window.screen = screen;


function getEnv(proxy_array) {
    for (let i = 0; i < proxy_array.length; i++) {
        handler = `{
            get: function(target, property, receiver) {
                   console.log('方法：get','    对象：${proxy_array[i]}','    属性：',property,'    属性类型：',typeof property,'    属性值类型：',typeof target[property]);
                   return target[property];
            },
            set: function(target, property, value, receiver){
                    console.log('方法：set','    对象：${proxy_array[i]}','    属性：',property,'    属性类型：',typeof property,'    属性值类型：',typeof target[property]);
                    return Reflect.set(...arguments);
            }
        }`;
        eval(`
            try {
                ${proxy_array[i]};
                ${proxy_array[i]} = new Proxy(${proxy_array[i]}, ${handler});
            } catch (e) {
                ${proxy_array[i]} = {};
                ${proxy_array[i]} = new Proxy(${proxy_array[i]}, ${handler});
            }
        `);
    }
}

proxy_array = ['window', 'document', 'location', 'navigator', 'history', 'screen']
getEnv(proxy_array);

require('./code');


//
var f = '/api/sns/web/v1/homefeed{"cursor_score":"","num":35,"refresh_type":1,"note_index":33,"unread_begin_note_id":"","unread_end_note_id":"","unread_note_count":0,"category":"homefeed_recommend","search_key":"","need_num":10,"image_formats":["jpg","webp","avif"],"need_filter_image":false}'
var c = "ab13ef8c64d47263db65846bf6947b30"
var d = "6cb167ba87e1a756420d916fc234803c"
console.log(window.mnsv2(f,c,d))
