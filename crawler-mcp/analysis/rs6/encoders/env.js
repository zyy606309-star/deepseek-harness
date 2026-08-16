content = "4u40jwi4XHuyXGUVUFj58jKj9KxO36Dj9BlMyW6hflRBYEcCi2WOlzV_NiUf4y2y";
!(function () {
    const $toString = Function.prototype.toString;
    const symbol = Symbol();
    const myToString = function () {
        return typeof this === "function" && this[symbol] || $toString.call(this);
    };
    function setNative(target, key, value) {
        Object.defineProperty(target, key, {
            enumerable: false,
            configurable: true,
            writable: true,
            value,
        });
    }
    delete Function.prototype.toString;
    setNative(Function.prototype, "toString", myToString);
    setNative(Function.prototype.toString, symbol, "function toString() { [native code] }");
    globalThis.safeFunction = function (func, funcname) {
        setNative(func, symbol, `function ${funcname || func.name || ""}() { [native code] }`);
        return func;
    };
})();

delete __filename;
delete __dirname;
window = global;
delete global;
window.window = window;
window.self = window;
window.top = window;

document = {};
location = {};
navigator = {};
history = {};
screen = {};

location.protocol = "http:";
location.host = "epub.cnipa.gov.cn";
location.hostname = "epub.cnipa.gov.cn";
location.pathname = "/";
location.href = "http://epub.cnipa.gov.cn/";
location.search = "";
location.hash = "";
location.port = "";
window.innerWidth = 1920;
window.innerHeight = 1080;
window.outerWidth = 1920;
window.outerHeight = 1080;

function Navigator() {}
safeFunction(Navigator);
navigator = new Navigator();
window.navigator = navigator;

Object.defineProperty(Navigator.prototype, "userAgent", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function userAgent() {
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36";
    }, "get userAgent")
});

Object.defineProperty(Navigator.prototype, "language", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function language() {
        return "zh-CN";
    }, "get language")
});

Object.defineProperty(Navigator.prototype, "languages", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function languages() {
        return ["zh-CN", "zh"];
    }, "get languages")
});

Object.defineProperty(Navigator.prototype, "platform", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function platform() {
        return "Win32";
    }, "get platform")
});

Object.defineProperty(Navigator.prototype, "webdriver", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function webdriver() {
        return false;
    }, "get webdriver")
});

Object.defineProperty(Navigator.prototype, "cookieEnabled", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function cookieEnabled() {
        return true;
    }, "get cookieEnabled")
});

window.CollectGarbage = undefined;
window.DOMParser = undefined;
window.ActiveXObject = undefined;

function XMLHttpRequest() {}
safeFunction(XMLHttpRequest);
Object.defineProperty(window, "XMLHttpRequest", {
    configurable: true,
    enumerable: false,
    writable: true,
    value: XMLHttpRequest
});

function Storage() {}
safeFunction(Storage);

Object.defineProperty(window, "localStorage", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function localStorage() {
        return {};
    }, "get localStorage")
});

Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function sessionStorage() {
        return {};
    }, "get sessionStorage")
});

function makeCollection(items) {
    const collection = {
        length: items.length,
        item: safeFunction(function item(index) {
            return items[index] || null;
        }, "item")
    };
    for (let i = 0; i < items.length; i++) {
        collection[i] = items[i];
    }
    return collection;
}

function makeElementLogger(name, target) {
    const logState = Object.create(null);
    return new Proxy(target, {
        get(currentTarget, property, receiver) {
            console.log(name + " get:", property, "type:", typeof currentTarget[property]);
            return Reflect.get(currentTarget, property, receiver);
        },
        set(currentTarget, property, value, receiver) {
            const key = String(property);
            if (key === "innerHTML") {
                logState[key] = (logState[key] || 0) + 1;
                if (logState[key] <= 5) {
                    console.log(name + " set:", property, "oldType:", typeof currentTarget[property], "newType:", typeof value);
                } else if (logState[key] === 6) {
                    console.log(name + " set:", property, "日志过多，后续同类输出已省略");
                }
                return Reflect.set(currentTarget, property, value, receiver);
            }
            console.log(name + " set:", property, "oldType:", typeof currentTarget[property], "newType:", typeof value);
            return Reflect.set(currentTarget, property, value, receiver);
        }
    });
}

function EventTarget() {}
safeFunction(EventTarget);
EventTarget.prototype.addEventListener = safeFunction(function addEventListener() {}, "addEventListener");
EventTarget.prototype.removeEventListener = safeFunction(function removeEventListener() {}, "removeEventListener");

function Node() {}
safeFunction(Node);
Object.setPrototypeOf(Node.prototype, EventTarget.prototype);
Node.prototype.appendChild = safeFunction(function appendChild(node) {
    return node;
}, "appendChild");
Node.prototype.removeChild = safeFunction(function removeChild(node) {
    return node;
}, "removeChild");

function Document() {}
safeFunction(Document);
Object.setPrototypeOf(Document.prototype, Node.prototype);
Object.defineProperty(Document.prototype, "documentElement", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function documentElement() {
        return {
            clientWidth: window.innerWidth,
            clientHeight: window.innerHeight
        };
    }, "get documentElement")
});
Object.defineProperty(Document.prototype, "visibilityState", {
    configurable: true,
    enumerable: true,
    get: safeFunction(function visibilityState() {
        return "visible";
    }, "get visibilityState")
});

function HTMLDocument() {}
safeFunction(HTMLDocument);
Object.setPrototypeOf(HTMLDocument.prototype, Document.prototype);
Document.prototype.getElementsByTagName = safeFunction(function getElementsByTagName(tagName) {
    console.log("Document.getElementsByTagName 参数:", tagName);
    const lowerTagName = String(tagName).toLowerCase();
    if (lowerTagName === "script") {
        return makeCollection([]);
    }
    if (lowerTagName === "base") {
        return makeCollection([]);
    }
    return makeCollection([]);
}, "getElementsByTagName");
Document.prototype.getElementById = safeFunction(function getElementById() {
    console.log("Document.getElementById 参数:", arguments[0]);
    return null;
}, "getElementById");

function Element() {}
safeFunction(Element);
Object.setPrototypeOf(Element.prototype, Node.prototype);
Element.prototype.getElementsByTagName = safeFunction(function getElementsByTagName(tagName) {
    console.log("Element.getElementsByTagName 参数:", tagName);
    const lowerTagName = String(tagName).toLowerCase();
    if (lowerTagName === "i") {
        return makeCollection([]);
    }
    return makeCollection([]);
}, "getElementsByTagName");
Element.prototype.setAttribute = safeFunction(function setAttribute(name, value) {
    console.log("Element.setAttribute 参数:", name, value);
    this[name] = value;
}, "setAttribute");
Element.prototype.addBehavior = safeFunction(function addBehavior() {}, "addBehavior");

function HTMLElement() {}
safeFunction(HTMLElement);
Object.setPrototypeOf(HTMLElement.prototype, Element.prototype);

function HTMLDivElement() {}
safeFunction(HTMLDivElement);
Object.setPrototypeOf(HTMLDivElement.prototype, HTMLElement.prototype);

function HTMLAnchorElement() {}
safeFunction(HTMLAnchorElement);
Object.setPrototypeOf(HTMLAnchorElement.prototype, HTMLElement.prototype);

function HTMLScriptElement() {}
safeFunction(HTMLScriptElement);
Object.setPrototypeOf(HTMLScriptElement.prototype, HTMLElement.prototype);

function HTMLBaseElement() {}
safeFunction(HTMLBaseElement);
Object.setPrototypeOf(HTMLBaseElement.prototype, HTMLElement.prototype);

function HTMLIElement() {}
safeFunction(HTMLIElement);
Object.setPrototypeOf(HTMLIElement.prototype, HTMLElement.prototype);

div = makeElementLogger("div", new HTMLDivElement());
div.style = {};

a = new HTMLAnchorElement();
scriptElement = makeElementLogger("script", new HTMLScriptElement());
scriptElement.parentNode = {
    removeChild: safeFunction(function removeChild(node) {
        return node;
    }, "removeChild")
};
baseElement = makeElementLogger("base", new HTMLBaseElement());
baseElement.href = "";
iElement = makeElementLogger("i", new HTMLIElement());

window.addEventListener = safeFunction(function addEventListener() {}, "addEventListener");
window.attachEvent = safeFunction(function attachEvent() {}, "attachEvent");
history.replaceState = safeFunction(function replaceState() {}, "replaceState");

document = new HTMLDocument();
window.document = document;

Document.prototype.createElement = safeFunction(function createElement(tagName) {
    console.log("document createElement 创建的标签为:", tagName);
    const lowerTagName = String(tagName).toLowerCase();
    if (lowerTagName === "div") {
        return div;
    }
    if (lowerTagName === "a") {
        return a;
    }
    return new HTMLElement();
}, "createElement");

function getEnv(proxy_array) {
    for (let i = 0; i < proxy_array.length; i++) {
        const handler = `{
            get: function(target, property, receiver) {
                console.log('方法：get','    对象：${proxy_array[i]}','    属性：',property,'    属性类型：',typeof property,'    属性值类型：',typeof target[property]);
                return target[property];
            },
            set: function(target, property, value, receiver) {
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

proxy_array = ["window", "document", "location", "navigator", "history", "screen","meta"];
getEnv(proxy_array);
