/* ProjectW 共通ヘルパー (One UI 風) */

/**
 * fetch ラッパー。form 形式 (application/x-www-form-urlencoded) で送信する。
 * @param {string} method  - "GET" / "POST" など
 * @param {string} url     - リクエスト先
 * @param {object|FormData} [formdata] - 送信データ (キー/値オブジェクト または FormData)
 * @returns {Promise<object>} 解析済み JSON
 * エラー時は alert を表示し、例外を再スローする。
 */
async function api(method, url, formdata) {
  const opts = { method: method, headers: {} };

  if (formdata && String(method).toUpperCase() !== "GET") {
    const params = new URLSearchParams();
    if (formdata instanceof FormData) {
      for (const [k, v] of formdata.entries()) params.append(k, v);
    } else {
      for (const k in formdata) {
        if (Object.prototype.hasOwnProperty.call(formdata, k)) {
          params.append(k, formdata[k]);
        }
      }
    }
    opts.body = params.toString();
    opts.headers["Content-Type"] = "application/x-www-form-urlencoded";
  }

  let res;
  try {
    res = await fetch(url, opts);
  } catch (netErr) {
    alert("通信エラーが発生しました。ネットワークをご確認ください。");
    throw netErr;
  }

  let data = {};
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try {
      data = await res.json();
    } catch (e) {
      data = {};
    }
  }

  if (!res.ok) {
    const m = (data && data.msg) ? data.msg : ("エラー: " + res.status + " " + res.statusText);
    alert(m);
    const err = new Error(m);
    err.response = res;
    err.data = data;
    throw err;
  }

  return data;
}

/**
 * トースト通知を表示する。
 * @param {string} message
 * @param {number} [duration=3000] 表示時間(ms)
 */
function toast(message, duration) {
  duration = duration || 3000;
  let container = document.querySelector(".toast-container");
  if (!container) {
    container = document.createElement("div");
    container.className = "toast-container";
    document.body.appendChild(container);
  }
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  container.appendChild(el);

  // reflow を強制してトランジションを発火
  void el.offsetWidth;
  el.classList.add("show");

  setTimeout(function () {
    el.classList.remove("show");
    setTimeout(function () {
      if (el.parentNode) el.remove();
      if (container.parentNode && container.children.length === 0) {
        container.remove();
      }
    }, 300);
  }, duration);
}

/* Service Worker 登録 (PWA) */
if ("serviceWorker" in navigator) {
  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/static/sw.js").catch(function () {
      /* SW 未配置でも無視 */
    });
  });
}
