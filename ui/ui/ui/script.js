// === Thanh điều hướng & giao diện sáng/tối ===
const navbar = document.getElementById('navbar');
const navToggle = document.getElementById('navToggle');
const navLinks = document.getElementById('navLinks');
const themeBtn = document.getElementById('themeBtn');

window.addEventListener('scroll', () => navbar.classList.toggle('scrolled', window.scrollY > 10));

navToggle.addEventListener('click', () => {
    const open = navLinks.classList.toggle('open');
    navToggle.setAttribute('aria-expanded', open);
});
navLinks.querySelectorAll('a').forEach(a => a.addEventListener('click', () => {
    navLinks.classList.remove('open');
    navToggle.setAttribute('aria-expanded', false);
}));

try {
    const saved = localStorage.getItem('theme');
    if (saved) document.documentElement.dataset.theme = saved;
} catch (e) { }

themeBtn.addEventListener('click', () => {
    const current = document.documentElement.dataset.theme
        || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch (e) { }
});

// === Hiệu ứng xuất hiện khi cuộn ===
const observer = new IntersectionObserver(entries => {
    entries.forEach(e => {
        if (e.isIntersecting) {
            e.target.classList.add('visible');
            observer.unobserve(e.target);
        }
    });
}, { threshold: 0.12 });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));

// === Demo: vẽ chữ ký ===
const pad = document.getElementById('sigPad');
const ctx = pad.getContext('2d');
const sigImg = document.getElementById('sigImg');
let drawing = false;

function resizePad() {
    const ratio = window.devicePixelRatio || 1;
    const rect = pad.getBoundingClientRect();
    pad.width = rect.width * ratio;
    pad.height = rect.height * ratio;
    ctx.scale(ratio, ratio);
    ctx.lineWidth = 2.4;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#1d3fa8';
    drawSample();
}

function drawSample() {
    const w = pad.getBoundingClientRect().width;
    ctx.clearRect(0, 0, w, 130);
    ctx.beginPath();
    ctx.moveTo(w * 0.18, 85);
    ctx.bezierCurveTo(w * 0.25, 20, w * 0.32, 110, w * 0.4, 60);
    ctx.bezierCurveTo(w * 0.47, 25, w * 0.5, 95, w * 0.58, 70);
    ctx.bezierCurveTo(w * 0.66, 45, w * 0.72, 90, w * 0.82, 55);
    ctx.stroke();
    updateSigImage();
}

function point(e) {
    const r = pad.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
}

pad.addEventListener('pointerdown', e => {
    drawing = true;
    pad.setPointerCapture(e.pointerId);
    const p = point(e);
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
});
pad.addEventListener('pointermove', e => {
    if (!drawing) return;
    const p = point(e);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
});
['pointerup', 'pointercancel'].forEach(t => pad.addEventListener(t, () => {
    if (drawing) { drawing = false; updateSigImage(); }
}));

function updateSigImage() {
    sigImg.src = pad.toDataURL('image/png');
    resetSigned();
}

document.getElementById('clearPad').addEventListener('click', () => {
    ctx.clearRect(0, 0, pad.width, pad.height);
    updateSigImage();
});

// Con dấu tròn minh họa
document.getElementById('stampPad').addEventListener('click', () => {
    const w = pad.getBoundingClientRect().width;
    const cx = w / 2, cy = 65, r = 52;
    ctx.clearRect(0, 0, w, 130);
    ctx.save();
    ctx.strokeStyle = '#dc2626';
    ctx.fillStyle = '#dc2626';
    ctx.lineWidth = 3;
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.arc(cx, cy, r - 9, 0, Math.PI * 2); ctx.stroke();
    ctx.font = '700 12px Inter, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('LAN CHAT', cx, cy - 6);
    ctx.font = '600 9px Inter, sans-serif';
    ctx.fillText('ĐÃ PHÊ DUYỆT', cx, cy + 10);
    ctx.font = '14px sans-serif';
    ctx.fillText('★', cx, cy + 28);
    ctx.restore();
    updateSigImage();
});

// === Demo: trang tài liệu & kéo thả ===
const paper = document.getElementById('paper');
const paperLines = document.getElementById('paperLines');
const sigBox = document.getElementById('sigBox');
const sigPos = document.getElementById('sigPos');
const sigTime = document.getElementById('sigTime');
let page = 1;
const positions = { 1: null, 2: null };

function renderPage() {
    const widths = page === 1 ? [100, 92, 97, 85, 100, 60, 94, 78] : [96, 100, 88, 100, 70];
    paperLines.innerHTML = '<div class="ttl"></div>' +
        widths.map(w => `<div class="ln" style="width:${w}%"></div>`).join('');
    const pos = positions[page];
    if (pos) {
        sigBox.style.left = pos.x + 'px';
        sigBox.style.top = pos.y + 'px';
    } else {
        sigBox.style.left = '';
        sigBox.style.top = '';
    }
    reportPos();
}

function reportPos() {
    sigPos.textContent = `Trang ${page} · x: ${Math.round(sigBox.offsetLeft)}, y: ${Math.round(sigBox.offsetTop)}`;
}

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

function moveTo(x, y) {
    x = clamp(x, 0, paper.clientWidth - sigBox.offsetWidth);
    y = clamp(y, 0, paper.clientHeight - sigBox.offsetHeight);
    sigBox.style.left = x + 'px';
    sigBox.style.top = y + 'px';
    positions[page] = { x, y };
    reportPos();
}

let drag = null;
sigBox.addEventListener('pointerdown', e => {
    drag = { dx: e.clientX - sigBox.offsetLeft, dy: e.clientY - sigBox.offsetTop };
    sigBox.setPointerCapture(e.pointerId);
    resetSigned();
});
sigBox.addEventListener('pointermove', e => {
    if (drag) moveTo(e.clientX - drag.dx, e.clientY - drag.dy);
});
['pointerup', 'pointercancel'].forEach(t => sigBox.addEventListener(t, () => drag = null));

// Di chuyển bằng phím mũi tên
sigBox.addEventListener('keydown', e => {
    const step = e.shiftKey ? 20 : 5;
    const map = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!map[e.key]) return;
    e.preventDefault();
    moveTo(sigBox.offsetLeft + map[e.key][0], sigBox.offsetTop + map[e.key][1]);
    resetSigned();
});

document.querySelectorAll('.demo-tabs button').forEach(btn => btn.addEventListener('click', () => {
    document.querySelectorAll('.demo-tabs button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    page = Number(btn.dataset.page);
    resetSigned();
    renderPage();
}));

// === Demo: ký ===
const toast = document.getElementById('toast');
function resetSigned() { sigBox.classList.remove('signed'); }

document.getElementById('signBtn').addEventListener('click', () => {
    const now = new Date();
    sigTime.textContent = 'Ngày ký: ' + now.toLocaleString('vi-VN');
    sigBox.classList.add('signed');
    toast.textContent = `✓ Đã ký số tại trang ${page}`;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2200);
});

sigTime.textContent = 'Ngày ký: ' + new Date().toLocaleDateString('vi-VN');
renderPage();
resizePad();
window.addEventListener('resize', () => { resizePad(); renderPage(); });
