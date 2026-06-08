// Frida WebView URL Hook — DeepSeek reference link capture
// Usage: frida -D <device> -p <pid> -l this.js

Java.perform(function() {
    console.log("[*] Frida WebView URL Hook starting...");

    // Hook 1: WebView.loadUrl(String)
    var WebView = Java.use("android.webkit.WebView");
    WebView.loadUrl.overload('java.lang.String').implementation = function(url) {
        if (url && url.indexOf("javascript:") !== 0) {
            console.log("[WebView.loadUrl] " + url);
        }
        return this.loadUrl(url);
    };

    // Hook 2: WebView.loadUrl(String, Map)
    WebView.loadUrl.overload('java.lang.String', 'java.util.Map').implementation = function(url, headers) {
        if (url && url.indexOf("javascript:") !== 0) {
            console.log("[WebView.loadUrl] " + url);
        }
        return this.loadUrl(url, headers);
    };

    // Hook 3: WebViewClient.shouldOverrideUrlLoading (String overload)
    var WebViewClient = Java.use("android.webkit.WebViewClient");
    WebViewClient.shouldOverrideUrlLoading.overload('android.webkit.WebView', 'java.lang.String').implementation = function(view, url) {
        if (url && url.indexOf("javascript:") !== 0) {
            console.log("[shouldOverrideUrlLoading] " + url);
        }
        return false;
    };

    // Hook 4: Intent.getData
    var Intent = Java.use("android.content.Intent");
    Intent.getData.implementation = function() {
        var uri = this.getData();
        if (uri !== null) {
            console.log("[Intent.getData] " + uri.toString());
        }
        return uri;
    };

    // Hook 5: URLSpan.onClick
    var URLSpan = Java.use("android.text.style.URLSpan");
    URLSpan.onClick.implementation = function(view) {
        var url = this.getURL();
        if (url) {
            console.log("[URLSpan.onClick] " + url);
        }
        return this.onClick(view);
    };

    console.log("[*] All hooks installed — 5 hooks active");
});
