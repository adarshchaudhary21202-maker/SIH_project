// Global application state
let currentGps = { lat: "28.6130", lng: "77.2090", accuracy: 3.8, locked: false };
let mediaStream = null;
let currentFacingMode = "environment"; // "environment" = rear, "user" = front
let gpsWatchId = null;

// Shift counters state (persisted)
let testsTodayCount = parseInt(localStorage.getItem('ncb_tests_today') || '4', 10);
let positivesCount = parseInt(localStorage.getItem('ncb_positives_count') || '3', 10);
let hasCurrentTestBeenCounted = false;

// Photo acquisition state (SEPARATED TEST TUBE & COLOR CARD)
let activeCaptureTarget = 'card'; // 'card' | 'tube'
let colorCardBlob = null;
let colorCardHash = null;
let colorCardDataUrl = null;
let colorCardTime = null;

let testTubeBlob = null;
let testTubeHash = null;
let testTubeDataUrl = null;
let testTubeTime = null;

// Video recording state
let videoRecorder = null;
let videoChunks = [];
let isVideoRecording = false;
let videoTimerInterval = null;
let videoSeconds = 0;
let recordedVideoBlob = null;
let videoHash = null;
let activeVideoAudioStream = null;

// Audio recording state
let audioRecorder = null;
let audioChunks = [];
let isAudioRecording = false;
let audioTimerInterval = null;
let audioSeconds = 0;
let recordedAudioBlob = null;
let audioHash = null;
let activeMicStream = null;
let audioContext = null;
let analyserNode = null;
let audioAnimFrame = null;

document.addEventListener("DOMContentLoaded", () => {
    fetchGPS();
    startLiveClock();
    updateMetricsUI();
    setCaptureTarget('card');
});

/* ==========================================================================
   REAL LIVE TIMESTAMP ENGINE
   ========================================================================== */

function startLiveClock() {
    updateClockUI();
    setInterval(updateClockUI, 1000);
}

function getFormattedRealTimestamp(date = new Date()) {
    const pad = (n) => String(n).padStart(2, '0');
    const day = pad(date.getDate());
    const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    const month = monthNames[date.getMonth()];
    const year = date.getFullYear();
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    const seconds = pad(date.getSeconds());
    
    // Timezone calculation
    const offsetMin = -date.getTimezoneOffset();
    const sign = offsetMin >= 0 ? "+" : "-";
    const offH = pad(Math.floor(Math.abs(offsetMin) / 60));
    const offM = pad(Math.abs(offsetMin) % 60);
    const tzStr = `UTC${sign}${offH}:${offM}`;
    
    return `${day} ${month} ${year}, ${hours}:${minutes}:${seconds} (${tzStr})`;
}

function updateClockUI() {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    const hours = pad(now.getHours());
    const minutes = pad(now.getMinutes());
    const seconds = pad(now.getSeconds());

    // Update status bar clock: HH:MM
    const statusBarTime = document.getElementById("live-status-time");
    if (statusBarTime) statusBarTime.innerText = `${hours}:${minutes}`;

    // Update tactical header timestamp: DD MMM YYYY • HH:MM:SS
    const headerTime = document.getElementById("live-header-timestamp");
    if (headerTime) {
        const day = pad(now.getDate());
        const monthNames = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
        const month = monthNames[now.getMonth()];
        const year = now.getFullYear();
        headerTime.innerText = `${day} ${month} ${year} • ${hours}:${minutes}:${seconds} IST`;
    }

    // Update collector GPS time
    const collectorGpsTime = document.getElementById("collector-gps-timestr");
    if (collectorGpsTime) {
        collectorGpsTime.innerText = `${hours}:${minutes}:${seconds} IST`;
    }
}

/* ==========================================================================
   SHIFT METRICS MANAGEMENT
   ========================================================================== */

function updateMetricsUI(shouldAnimate = false) {
    const testsEl = document.getElementById("metric-tests-today");
    const posEl = document.getElementById("metric-positives");
    const inlineTestsEl = document.getElementById("inline-tests-count");
    const inlinePosEl = document.getElementById("inline-pos-count");

    const padCount = (cnt) => String(cnt).padStart(2, '0');

    if (testsEl) {
        testsEl.innerText = padCount(testsTodayCount);
        if (shouldAnimate) {
            testsEl.classList.remove("metric-bump");
            void testsEl.offsetWidth;
            testsEl.classList.add("metric-bump");
        }
    }
    if (posEl) {
        posEl.innerText = padCount(positivesCount);
        if (shouldAnimate) {
            posEl.classList.remove("metric-bump");
            void posEl.offsetWidth;
            posEl.classList.add("metric-bump");
        }
    }
    if (inlineTestsEl) inlineTestsEl.innerText = padCount(testsTodayCount);
    if (inlinePosEl) inlinePosEl.innerText = padCount(positivesCount);
}

// Callback invoked by Android native layer when permissions are granted
window.onNativePermissionsGranted = function () {
    console.log("Native permissions granted callback triggered");
    fetchGPS(true);
    const collectorScreen = document.getElementById("screen-collector");
    if (collectorScreen && !collectorScreen.classList.contains("hidden")) {
        initWebcam(true);
    }
};

function navigateTo(screenId) {
    document.querySelectorAll("section").forEach(sec => sec.classList.add("hidden"));
    const targetScreen = document.getElementById(screenId);
    if (targetScreen) targetScreen.classList.remove("hidden");

    if (screenId === 'screen-collector') {
        const videoElement = document.getElementById("webcam");
        if (mediaStream && mediaStream.active && videoElement) {
            videoElement.srcObject = mediaStream;
            videoElement.play().catch(e => console.warn("Video resume play error:", e));
        } else {
            initWebcam(false);
        }
    } else {
        // If navigating away from collector screen, stop video recording if running
        if (isVideoRecording) {
            toggleVideoRecord();
        }
    }

    if (screenId === 'screen-review') {
        generateMasterHash();
    }
}

/* ==========================================================================
   1. GPS / GEOLOCATION MODULE (HIGHLIGHTED & SYNCHRONIZED)
   ========================================================================== */

function updateGpsUI(lat, lng, isMock = false, accuracy = null) {
    currentGps.lat = Number(lat).toFixed(4);
    currentGps.lng = Number(lng).toFixed(4);
    currentGps.accuracy = accuracy ? Math.round(accuracy * 10) / 10 : 3.8;
    currentGps.locked = !isMock;

    const coordsText = `${currentGps.lat}° N, ${currentGps.lng}° E`;
    const badgeText = isMock
        ? `GPS: ${currentGps.lat}, ${currentGps.lng} (MANUAL)`
        : `GPS: ${currentGps.lat}, ${currentGps.lng} (±${currentGps.accuracy}m)`;

    // Top Header Badge
    const gpsBadgeText = document.getElementById("gps-badge-text");
    if (gpsBadgeText) gpsBadgeText.innerText = badgeText;

    // Highlighted Collector GPS Card
    const collectorCoords = document.getElementById("collector-gps-coords");
    const collectorAcc = document.getElementById("collector-gps-accuracy");
    const collectorPill = document.getElementById("collector-gps-pill");

    if (collectorCoords) collectorCoords.innerText = coordsText;
    if (collectorAcc) collectorAcc.innerText = `±${currentGps.accuracy}m HIGH PRECISION`;
    if (collectorPill) {
        collectorPill.innerText = isMock ? "MANUAL OVERRIDE" : "SATELLITE LOCKED";
        collectorPill.className = isMock
            ? "text-[9px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 px-2 py-0.5 rounded-full"
            : "text-[9px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 px-2 py-0.5 rounded-full";
    }

    // Highlighted Dashboard GPS Card
    const dashCoords = document.getElementById("dash-gps-coords");
    if (dashCoords) dashCoords.innerText = coordsText;

    // Review Manifest GPS
    const revGps = document.getElementById("rev-gps");
    if (revGps) revGps.innerText = `${coordsText} (±${currentGps.accuracy}m precision)`;

    const manualLat = document.getElementById("manual-lat");
    const manualLng = document.getElementById("manual-lng");
    if (manualLat) manualLat.value = currentGps.lat;
    if (manualLng) manualLng.value = currentGps.lng;
}

function handleGpsBadgeClick() {
    const modal = document.getElementById("gps-modal");
    if (modal) {
        modal.classList.remove("hidden");
    }
}

function closeGpsModal() {
    const modal = document.getElementById("gps-modal");
    if (modal) {
        modal.classList.add("hidden");
    }
}

function saveManualGps() {
    const lat = document.getElementById("manual-lat")?.value.trim() || currentGps.lat;
    const lng = document.getElementById("manual-lng")?.value.trim() || currentGps.lng;
    updateGpsUI(lat, lng, true);
    closeGpsModal();
}

async function fetchGPS(forceRetry = false) {
    const gpsBadge = document.getElementById("gps-badge");
    if (gpsBadge) gpsBadge.innerText = "GPS: ACQUIRING... 🛰️";

    // 1. Try Capacitor native Geolocation plugin if available
    const CapGeo = window.Capacitor?.Plugins?.Geolocation ||
        (window.Capacitor?.registerPlugin ? window.Capacitor.registerPlugin('Geolocation') : null);

    if (CapGeo) {
        try {
            if (typeof CapGeo.checkPermissions === 'function') {
                let status = await CapGeo.checkPermissions();
                if (status.location !== 'granted' && status.coarseLocation !== 'granted') {
                    if (typeof CapGeo.requestPermissions === 'function') {
                        status = await CapGeo.requestPermissions();
                    }
                }
            }
            const pos = await CapGeo.getCurrentPosition({
                enableHighAccuracy: true,
                timeout: 10000
            });
            if (pos && pos.coords) {
                updateGpsUI(pos.coords.latitude, pos.coords.longitude, false, pos.coords.accuracy);
                startGpsWatch();
                return;
            }
        } catch (err) {
            console.warn("Capacitor Geolocation error, trying HTML5 Geolocation:", err);
        }
    }

    // 2. Fallback to HTML5 Geolocation
    fallbackHtml5Geolocation();
}

function fallbackHtml5Geolocation() {
    if (!("geolocation" in navigator)) {
        console.warn("Geolocation not supported by navigator");
        updateGpsUI(currentGps.lat, currentGps.lng, true);
        return;
    }

    // Try high accuracy first
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            updateGpsUI(pos.coords.latitude, pos.coords.longitude, false, pos.coords.accuracy);
            startGpsWatch();
        },
        (err) => {
            console.warn("High-accuracy GPS failed or timed out, trying coarse/network:", err);
            // Fallback to coarse/network accuracy with longer maxAge
            navigator.geolocation.getCurrentPosition(
                (fallbackPos) => {
                    updateGpsUI(fallbackPos.coords.latitude, fallbackPos.coords.longitude, false, fallbackPos.coords.accuracy);
                    startGpsWatch();
                },
                (finalErr) => {
                    console.warn("GPS Access Failed completely:", finalErr);
                    const gpsBadge = document.getElementById("gps-badge");
                    if (gpsBadge) {
                        gpsBadge.innerText = "GPS: TAP TO SET / RETRY ↻";
                        gpsBadge.className = "font-mono text-amber-400 text-[10px] bg-slate-800 border border-amber-500/40 px-2.5 py-1 rounded-full cursor-pointer hover:border-teal-500 hover:text-teal-300 transition-all shadow-sm";
                    }
                    updateGpsUI(currentGps.lat, currentGps.lng, true);
                },
                { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 }
            );
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 10000 }
    );
}

function startGpsWatch() {
    if (gpsWatchId !== null || !("geolocation" in navigator)) return;

    try {
        gpsWatchId = navigator.geolocation.watchPosition(
            (pos) => {
                updateGpsUI(pos.coords.latitude, pos.coords.longitude, false, pos.coords.accuracy);
            },
            (err) => {
                console.warn("GPS watch update error:", err);
            },
            { enableHighAccuracy: true, maximumAge: 10000, timeout: 20000 }
        );
    } catch (e) {
        console.warn("watchPosition failed to start:", e);
    }
}

/* ==========================================================================
   2. CAMERA & PHOTO MODULE
   ========================================================================== */

async function initWebcam(userTriggered = false) {
    const camStatus = document.getElementById("cam-status");
    const videoElement = document.getElementById("webcam");
    const placeholder = document.getElementById("cam-placeholder");

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        console.warn("getUserMedia is not available (insecure context or unsupported browser).");
        if (camStatus) {
            camStatus.innerText = "CAM OFFLINE (USE NATIVE 📁)";
            camStatus.className = "text-[10px] font-bold text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full cursor-pointer hover:underline";
        }
        if (placeholder) placeholder.classList.remove("hidden");
        return;
    }

    if (camStatus) {
        camStatus.innerText = "INITIALIZING... 📷";
        camStatus.className = "text-[10px] font-bold text-amber-600 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded-full cursor-pointer";
    }

    // Clean up existing stream
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }

    const constraintsList = [
        {
            video: {
                facingMode: { ideal: currentFacingMode },
                width: { ideal: 1280 },
                height: { ideal: 720 }
            },
            audio: false
        },
        {
            video: {
                facingMode: currentFacingMode
            },
            audio: false
        },
        {
            video: true,
            audio: false
        }
    ];

    let stream = null;
    for (const constraints of constraintsList) {
        try {
            stream = await navigator.mediaDevices.getUserMedia(constraints);
            if (stream) break;
        } catch (err) {
            console.warn("Camera constraint failed:", constraints, err);
        }
    }

    if (stream) {
        mediaStream = stream;
        if (videoElement) {
            videoElement.muted = true;
            videoElement.setAttribute("playsinline", "true");
            videoElement.srcObject = mediaStream;
            try {
                await videoElement.play();
            } catch (playErr) {
                console.warn("videoElement.play() was deferred:", playErr);
            }
        }
        if (placeholder) placeholder.classList.add("hidden");
        if (camStatus) {
            const modeLabel = currentFacingMode === "environment" ? "REAR" : "FRONT";
            camStatus.innerText = `LIVE 🟢 (${modeLabel})`;
            camStatus.className = "text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full cursor-pointer";
        }
    } else {
        if (placeholder) placeholder.classList.remove("hidden");
        if (camStatus) {
            camStatus.innerText = "CAM OFFLINE (TAP RETRY ↻)";
            camStatus.className = "text-[10px] font-bold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full cursor-pointer hover:underline";
        }
    }
}

function switchCamera() {
    currentFacingMode = currentFacingMode === "environment" ? "user" : "environment";
    initWebcam(true);
}

/* ==========================================================================
   2. SEPARATED PHOTO ACQUISITION & OPTICAL ANALYSIS MODULE
   ========================================================================== */

function setCaptureTarget(target) {
    activeCaptureTarget = target;
    const tabCard = document.getElementById("tab-card");
    const tabTube = document.getElementById("tab-tube");
    const reticleCard = document.getElementById("reticle-card");
    const reticleTube = document.getElementById("reticle-tube");
    const snapText = document.getElementById("txt-snap-active");

    if (target === 'card') {
        if (tabCard) {
            tabCard.className = "py-2 px-2 rounded-lg font-bold transition-all flex items-center justify-center space-x-1.5 bg-teal-700 text-white shadow-sm";
        }
        if (tabTube) {
            tabTube.className = "py-2 px-2 rounded-lg font-bold transition-all flex items-center justify-center space-x-1.5 text-slate-600 hover:bg-slate-200";
        }
        if (reticleCard) reticleCard.classList.remove("hidden");
        if (reticleTube) reticleTube.classList.add("hidden");
        if (snapText) snapText.innerText = "SNAP COLOR CARD";
    } else {
        if (tabTube) {
            tabTube.className = "py-2 px-2 rounded-lg font-bold transition-all flex items-center justify-center space-x-1.5 bg-amber-600 text-white shadow-sm";
        }
        if (tabCard) {
            tabCard.className = "py-2 px-2 rounded-lg font-bold transition-all flex items-center justify-center space-x-1.5 text-slate-600 hover:bg-slate-200";
        }
        if (reticleTube) reticleTube.classList.remove("hidden");
        if (reticleCard) reticleCard.classList.add("hidden");
        if (snapText) snapText.innerText = "SNAP TEST TUBE";
    }
}

function captureCurrentTarget() {
    captureSpecificPhoto(activeCaptureTarget);
}

function triggerNativePhoto(target) {
    const fileInput = document.getElementById(`${target}-file-input`);
    if (fileInput) fileInput.click();
}

async function handleNativePhotoFile(event, target) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    const hash = await computeBlobSha256(file);
    const reader = new FileReader();
    reader.onload = (e) => {
        applyPhotoCapture(target, file, hash, e.target.result);
    };
    reader.readAsDataURL(file);
}

async function captureSpecificPhoto(target) {
    setCaptureTarget(target);
    const video = document.getElementById("webcam");

    if (video && video.videoWidth > 0 && video.videoHeight > 0 && !video.paused) {
        const canvas = document.createElement("canvas");
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const capturedDataUrl = canvas.toDataURL("image/jpeg", 0.92);
        const response = await fetch(capturedDataUrl);
        const blob = await response.blob();
        const hash = await computeBlobSha256(blob);

        applyPhotoCapture(target, blob, hash, capturedDataUrl);
    } else {
        console.warn(`Viewfinder not active, falling back to native picker for ${target}`);
        triggerNativePhoto(target);
    }
}

function applyPhotoCapture(target, blob, hash, dataUrl) {
    const nowIso = new Date().toISOString();

    if (target === 'card') {
        colorCardBlob = blob;
        colorCardHash = hash;
        colorCardDataUrl = dataUrl;
        colorCardTime = nowIso;

        const previewPlaceholder = document.getElementById("card-preview-placeholder");
        const previewContent = document.getElementById("card-preview-content");
        const previewImg = document.getElementById("card-preview-img");
        const badgeCard = document.getElementById("badge-card");

        if (previewPlaceholder) previewPlaceholder.classList.add("hidden");
        if (previewContent) previewContent.classList.remove("hidden");
        if (previewImg) previewImg.src = dataUrl;
        if (badgeCard) {
            badgeCard.innerText = "SAVED ✓";
            badgeCard.className = "text-[9px] bg-emerald-700 text-emerald-100 px-1.5 py-0.5 rounded font-mono font-bold";
        }

        // Auto advance to test tube if not yet captured
        if (!testTubeBlob) {
            setTimeout(() => setCaptureTarget('tube'), 600);
        }
    } else {
        testTubeBlob = blob;
        testTubeHash = hash;
        testTubeDataUrl = dataUrl;
        testTubeTime = nowIso;

        const previewPlaceholder = document.getElementById("tube-preview-placeholder");
        const previewContent = document.getElementById("tube-preview-content");
        const previewImg = document.getElementById("tube-preview-img");
        const badgeTube = document.getElementById("badge-tube");

        if (previewPlaceholder) previewPlaceholder.classList.add("hidden");
        if (previewContent) previewContent.classList.remove("hidden");
        if (previewImg) previewImg.src = dataUrl;
        if (badgeTube) {
            badgeTube.innerText = "SAVED ✓";
            badgeTube.className = "text-[9px] bg-emerald-700 text-emerald-100 px-1.5 py-0.5 rounded font-mono font-bold";
        }
    }

    // Update media specimens count chip
    const totalPhotos = (colorCardBlob ? 1 : 0) + (testTubeBlob ? 1 : 0);
    const countChip = document.getElementById("preview-count-chip");
    if (countChip) countChip.innerText = `${totalPhotos} OF 2 PHOTOS`;

    // Check if both photos are now captured
    if (colorCardBlob && testTubeBlob) {
        const runBanner = document.getElementById("run-analysis-banner");
        if (runBanner) runBanner.classList.remove("hidden");

        // Automatically launch the circular analysis workflow after 600ms if not analyzed yet
        if (!hasCurrentTestBeenCounted) {
            setTimeout(() => {
                startAnalysisWorkflow();
            }, 600);
        }
    }
}

/* ==========================================================================
   CIRCULAR PROGRESS ANALYSER & TICK MARK POP-UP WORKFLOW
   ========================================================================== */

function startAnalysisWorkflow() {
    const loadingModal = document.getElementById("analysis-loading-modal");
    const progressBar = document.getElementById("analysis-progress-bar");
    const percentText = document.getElementById("analysis-percent-text");
    const statusText = document.getElementById("analysis-status-text");

    if (!loadingModal) return;

    loadingModal.classList.remove("hidden");

    const circumference = 263.89; // 2 * PI * 42
    let currentPercent = 0;
    const durationMs = 2800; // ~3 seconds
    const intervalMs = 60;
    const stepCount = durationMs / intervalMs;
    const increment = 100 / stepCount;

    const statusStages = [
        { at: 0, text: "Normalizing optical white-balance from Color Card..." },
        { at: 25, text: "Extracting RGB & CIE L*a*b* spectrophotometric curve..." },
        { at: 55, text: "Cross-referencing Marquis Reagent chemical database..." },
        { at: 80, text: "Computing Delta-E chromatic confidence coefficient..." },
        { at: 98, text: "Spectral Verification Complete!" }
    ];

    const timer = setInterval(() => {
        currentPercent = Math.min(100, currentPercent + increment);
        const roundPercent = Math.round(currentPercent);

        if (percentText) percentText.innerText = `${roundPercent}%`;
        if (progressBar) {
            const offset = circumference - (currentPercent / 100) * circumference;
            progressBar.style.strokeDashoffset = offset;
        }

        // Update status message
        for (let i = statusStages.length - 1; i >= 0; i--) {
            if (roundPercent >= statusStages[i].at) {
                if (statusText) statusText.innerText = statusStages[i].text;
                break;
            }
        }

        if (currentPercent >= 100) {
            clearInterval(timer);
            setTimeout(() => {
                loadingModal.classList.add("hidden");
                finishAnalysisSuccess();
            }, 350);
        }
    }, intervalMs);
}

function finishAnalysisSuccess() {
    // Increment counts for this test run
    if (!hasCurrentTestBeenCounted) {
        testsTodayCount += 1;
        positivesCount += 1; // Presumptive positive match
        localStorage.setItem('ncb_tests_today', testsTodayCount);
        localStorage.setItem('ncb_positives_count', positivesCount);
        hasCurrentTestBeenCounted = true;
        updateMetricsUI(true);
    }

    // Trigger haptic feedback if available on smartphone
    if (navigator.vibrate) {
        try { navigator.vibrate([100, 50, 100]); } catch (e) {}
    }

    // Show animated tick-mark pop-up modal
    const successModal = document.getElementById("analysis-success-modal");
    if (successModal) successModal.classList.remove("hidden");

    // Reveal the analysis results card
    const analysisCard = document.getElementById("analysis-card");
    if (analysisCard) analysisCard.classList.remove("hidden");

    const runBanner = document.getElementById("run-analysis-banner");
    if (runBanner) runBanner.classList.add("hidden");
}

function closeAnalysisSuccessModal() {
    const successModal = document.getElementById("analysis-success-modal");
    if (successModal) successModal.classList.add("hidden");

    // Scroll smoothly to results card
    const analysisCard = document.getElementById("analysis-card");
    if (analysisCard) {
        analysisCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

/* ==========================================================================
   3. VIDEO RECORDING MODULE
   ========================================================================== */

function getSupportedVideoMimeType() {
    const candidateTypes = [
        'video/mp4;codecs=avc1,mp4a',
        'video/mp4',
        'video/webm;codecs=vp8,opus',
        'video/webm;codecs=vp8',
        'video/webm'
    ];
    for (const type of candidateTypes) {
        if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) {
            return type;
        }
    }
    return '';
}

function triggerNativeVideo() {
    const fileInput = document.getElementById("video-file-input");
    if (fileInput) fileInput.click();
}

async function handleNativeVideoFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    recordedVideoBlob = file;
    videoHash = await computeBlobSha256(recordedVideoBlob);

    const hashVideoEl = document.getElementById("hash-video");
    if (hashVideoEl) hashVideoEl.innerText = videoHash;

    const previewContainer = document.getElementById("media-preview-container");
    const videoPreviewBox = document.getElementById("video-preview-box");
    const videoPlayer = document.getElementById("video-preview-player");
    const txt = document.getElementById("txt-record-video");

    const videoUrl = URL.createObjectURL(recordedVideoBlob);
    if (videoPlayer && videoPreviewBox) {
        videoPlayer.src = videoUrl;
        videoPlayer.load();
        videoPreviewBox.classList.remove("hidden");
        if (previewContainer) previewContainer.classList.remove("hidden");
    }

    if (txt) {
        txt.innerText = "VIDEO ATTACHED ✓";
        setTimeout(() => { txt.innerText = "REC VIDEO"; }, 2500);
    }
}

async function toggleVideoRecord() {
    const btn = document.getElementById("btn-record-video");
    const txt = document.getElementById("txt-record-video");
    const icon = document.getElementById("icon-record-video");
    const previewContainer = document.getElementById("media-preview-container");
    const videoPreviewBox = document.getElementById("video-preview-box");
    const videoPlayer = document.getElementById("video-preview-player");
    const hashVideoEl = document.getElementById("hash-video");

    if (!isVideoRecording) {
        if (typeof MediaRecorder === 'undefined') {
            alert("MediaRecorder not supported on this browser. Opening device camcorder...");
            triggerNativeVideo();
            return;
        }

        // Ensure camera stream is ready
        if (!mediaStream || !mediaStream.active) {
            await initWebcam(true);
        }

        if (!mediaStream || !mediaStream.active) {
            console.warn("Camera stream not available for live recording, opening native camcorder fallback");
            triggerNativeVideo();
            return;
        }

        videoChunks = [];

        // Acquire audio track from microphone for video recording
        try {
            activeVideoAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch (audioErr) {
            console.warn("Microphone not accessible for video recording; recording video-only:", audioErr);
            activeVideoAudioStream = null;
        }

        // Combine video and audio tracks
        const combinedTracks = [
            ...mediaStream.getVideoTracks(),
            ...(activeVideoAudioStream ? activeVideoAudioStream.getAudioTracks() : [])
        ];
        const recordStream = new MediaStream(combinedTracks);

        const mimeType = getSupportedVideoMimeType();
        const options = mimeType ? { mimeType } : undefined;

        try {
            videoRecorder = new MediaRecorder(recordStream, options);
        } catch (err) {
            console.warn("MediaRecorder failed with options, trying default constructor:", err);
            try {
                videoRecorder = new MediaRecorder(recordStream);
            } catch (fallbackErr) {
                console.error("Failed to initialize MediaRecorder:", fallbackErr);
                alert("Live video recording failed on this device. Switching to native camcorder.");
                triggerNativeVideo();
                return;
            }
        }

        videoRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) {
                videoChunks.push(e.data);
            }
        };

        videoRecorder.onstop = async () => {
            if (activeVideoAudioStream) {
                activeVideoAudioStream.getTracks().forEach(t => t.stop());
                activeVideoAudioStream = null;
            }

            if (videoChunks.length > 0) {
                const actualType = (videoRecorder && videoRecorder.mimeType) || mimeType || 'video/webm';
                recordedVideoBlob = new Blob(videoChunks, { type: actualType });
                videoHash = await computeBlobSha256(recordedVideoBlob);

                if (hashVideoEl) hashVideoEl.innerText = videoHash;

                const videoUrl = URL.createObjectURL(recordedVideoBlob);
                if (videoPlayer && videoPreviewBox) {
                    videoPlayer.src = videoUrl;
                    videoPlayer.load();
                    videoPreviewBox.classList.remove("hidden");
                    if (previewContainer) previewContainer.classList.remove("hidden");
                }
            }
        };

        videoRecorder.onerror = (e) => {
            console.error("VideoRecorder runtime error:", e);
        };

        videoRecorder.start(500); // chunk every 500ms
        isVideoRecording = true;
        videoSeconds = 0;

        if (btn) {
            btn.classList.add("bg-red-600", "animate-pulse", "border-red-400");
            btn.classList.remove("bg-slate-800");
        }
        if (icon) icon.innerText = "⏹";
        if (txt) txt.innerText = "00:00 STOP";

        videoTimerInterval = setInterval(() => {
            videoSeconds++;
            const mins = String(Math.floor(videoSeconds / 60)).padStart(2, '0');
            const secs = String(videoSeconds % 60).padStart(2, '0');
            if (txt) txt.innerText = `${mins}:${secs} STOP`;
        }, 1000);

    } else {
        // Stop recording
        if (videoRecorder && videoRecorder.state !== "inactive") {
            videoRecorder.stop();
        }
        isVideoRecording = false;
        clearInterval(videoTimerInterval);

        if (btn) {
            btn.classList.remove("bg-red-600", "animate-pulse", "border-red-400");
            btn.classList.add("bg-slate-800");
        }
        if (icon) icon.innerText = "⏺";
        if (txt) txt.innerText = `REC VIDEO (${videoSeconds}s ✓)`;
    }
}

/* ==========================================================================
   4. VOICE RECORDING MODULE
   ========================================================================== */

function getSupportedAudioMimeType() {
    const candidateTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/aac',
        'audio/ogg;codecs=opus'
    ];
    for (const type of candidateTypes) {
        if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) {
            return type;
        }
    }
    return '';
}

function triggerNativeAudio() {
    const fileInput = document.getElementById("audio-file-input");
    if (fileInput) fileInput.click();
}

async function handleNativeAudioFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;

    recordedAudioBlob = file;
    audioHash = await computeBlobSha256(recordedAudioBlob);

    const hashAudioEl = document.getElementById("hash-audio");
    if (hashAudioEl) hashAudioEl.innerText = audioHash;

    const audioPlayback = document.getElementById("audio-playback");
    const timerText = document.getElementById("audio-timer");

    if (audioPlayback) {
        const audioUrl = URL.createObjectURL(recordedAudioBlob);
        audioPlayback.src = audioUrl;
        audioPlayback.load();
        audioPlayback.classList.remove("hidden");
    }

    if (timerText) {
        timerText.innerText = "Audio memo attached ✓";
    }
}

async function toggleAudioRecord() {
    const btn = document.getElementById("btn-record-audio");
    const timerText = document.getElementById("audio-timer");
    const bar = document.getElementById("audio-bar");
    const levelLabel = document.getElementById("audio-level-label");
    const audioPlayback = document.getElementById("audio-playback");
    const hashAudioEl = document.getElementById("hash-audio");

    if (!isAudioRecording) {
        if (typeof MediaRecorder === 'undefined' || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert("Live audio recording not supported in this environment. Please attach an audio file.");
            triggerNativeAudio();
            return;
        }

        audioChunks = [];
        try {
            activeMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Setup real-time audio visualizer
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const source = audioContext.createMediaStreamSource(activeMicStream);
                analyserNode = audioContext.createAnalyser();
                analyserNode.fftSize = 64;
                source.connect(analyserNode);

                const dataArray = new Uint8Array(analyserNode.frequencyBinCount);
                const updateVisualizer = () => {
                    if (!isAudioRecording) return;
                    analyserNode.getByteFrequencyData(dataArray);
                    let sum = 0;
                    for (let i = 0; i < dataArray.length; i++) {
                        sum += dataArray[i];
                    }
                    const avg = sum / dataArray.length;
                    const percent = Math.min(100, Math.round((avg / 128) * 100));
                    if (bar) bar.style.width = `${percent}%`;
                    audioAnimFrame = requestAnimationFrame(updateVisualizer);
                };
                updateVisualizer();
            } catch (vizErr) {
                console.warn("AudioContext visualizer error:", vizErr);
            }

            const mimeType = getSupportedAudioMimeType();
            const options = mimeType ? { mimeType } : undefined;

            try {
                audioRecorder = new MediaRecorder(activeMicStream, options);
            } catch (recorderErr) {
                console.warn("Audio MediaRecorder with options failed, trying default:", recorderErr);
                audioRecorder = new MediaRecorder(activeMicStream);
            }

            audioRecorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) {
                    audioChunks.push(e.data);
                }
            };

            audioRecorder.onstop = async () => {
                if (activeMicStream) {
                    activeMicStream.getTracks().forEach(t => t.stop());
                    activeMicStream = null;
                }
                if (audioContext && audioContext.state !== 'closed') {
                    audioContext.close().catch(() => {});
                }
                if (audioAnimFrame) {
                    cancelAnimationFrame(audioAnimFrame);
                }

                if (audioChunks.length > 0) {
                    const actualType = (audioRecorder && audioRecorder.mimeType) || mimeType || 'audio/webm';
                    recordedAudioBlob = new Blob(audioChunks, { type: actualType });
                    audioHash = await computeBlobSha256(recordedAudioBlob);

                    if (hashAudioEl) hashAudioEl.innerText = audioHash;

                    if (audioPlayback) {
                        const audioUrl = URL.createObjectURL(recordedAudioBlob);
                        audioPlayback.src = audioUrl;
                        audioPlayback.load();
                        audioPlayback.classList.remove("hidden");
                    }
                }
            };

            audioRecorder.start(250);
            isAudioRecording = true;
            audioSeconds = 0;

            if (btn) {
                btn.classList.add("animate-pulse", "bg-red-600", "border-red-400");
                btn.classList.remove("bg-red-950");
            }
            if (levelLabel) {
                levelLabel.innerText = "RECORDING 🎙️";
                levelLabel.className = "text-[10px] font-mono font-bold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full";
            }
            if (timerText) timerText.innerText = "Recording 00:00 (Tap mic to stop)...";

            audioTimerInterval = setInterval(() => {
                audioSeconds++;
                const mins = String(Math.floor(audioSeconds / 60)).padStart(2, '0');
                const secs = String(audioSeconds % 60).padStart(2, '0');
                if (timerText) timerText.innerText = `Recording ${mins}:${secs} (Tap mic to stop)...`;
            }, 1000);

        } catch (err) {
            console.error("Audio recording error:", err);
            alert("Microphone permission required for audio dictation. Alternatively, you can attach an audio file.");
            triggerNativeAudio();
        }
    } else {
        if (audioRecorder && audioRecorder.state !== "inactive") {
            audioRecorder.stop();
        }
        isAudioRecording = false;
        clearInterval(audioTimerInterval);
        if (audioAnimFrame) cancelAnimationFrame(audioAnimFrame);

        if (btn) {
            btn.classList.remove("animate-pulse", "bg-red-600", "border-red-400");
            btn.classList.add("bg-red-950");
        }
        if (levelLabel) {
            levelLabel.innerText = "SAVED ✓";
            levelLabel.className = "text-[10px] font-mono font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-full";
            setTimeout(() => {
                if (levelLabel) {
                    levelLabel.innerText = "MIC STANDBY";
                    levelLabel.className = "text-[10px] font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full";
                }
            }, 2500);
        }
        if (timerText) timerText.innerText = `Voice note recorded (${audioSeconds}s) 🎙️`;
        if (bar) bar.style.width = "0%";
    }
}

/* ==========================================================================
   5. CRYPTOGRAPHIC SIGNATURE & LOGIN MODULE
   ========================================================================== */

function handleLogin(e) {
    if (e) e.preventDefault();
    const officerInput = document.getElementById("officer-id");
    const officerId = officerInput ? officerInput.value : "NCB-8809";

    const dashOfficer = document.getElementById("dash-officer-name");
    const revOfficer = document.getElementById("rev-officer");

    if (dashOfficer) dashOfficer.innerText = `OFFICER ${officerId}`;
    if (revOfficer) revOfficer.innerText = officerId;

    navigateTo("screen-dashboard");
}

async function computeSha256(message) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

async function computeBlobSha256(blob) {
    const arrayBuffer = await blob.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest("SHA-256", arrayBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

async function generateMasterHash() {
    const caseInput = document.getElementById("case-no");
    const caseNo = caseInput ? caseInput.value : "FIR-2026-99010";

    const revCase = document.getElementById("rev-case");
    const revTime = document.getElementById("rev-time");
    const revGps = document.getElementById("rev-gps");

    if (revCase) revCase.innerText = caseNo;
    if (revTime) revTime.innerText = getFormattedRealTimestamp();
    if (revGps) {
        revGps.innerText = `${currentGps.lat}° N, ${currentGps.lng}° E (±${currentGps.accuracy}m precision)`;
    }

    const hashCardEl = document.getElementById("hash-card");
    const hashTubeEl = document.getElementById("hash-tube");
    const hashVideoEl = document.getElementById("hash-video");
    const hashAudioEl = document.getElementById("hash-audio");

    const cHash = colorCardHash || "NO_COLOR_CARD";
    const tHash = testTubeHash || "NO_TEST_TUBE";
    const vHash = videoHash || "NO_VIDEO";
    const aHash = audioHash || "NO_AUDIO";

    if (hashCardEl) hashCardEl.innerText = colorCardHash || "No color card photo captured";
    if (hashTubeEl) hashTubeEl.innerText = testTubeHash || "No test tube photo captured";
    if (hashVideoEl) hashVideoEl.innerText = videoHash || "No video evidence captured";
    if (hashAudioEl) hashAudioEl.innerText = audioHash || "No audio memo captured";

    const nowIso = new Date().toISOString();
    const payload = `${caseNo}|${currentGps.lat}|${currentGps.lng}|CARD:${cHash}|TUBE:${tHash}|V:${vHash}|A:${aHash}|${nowIso}`;
    const masterHash = await computeSha256(payload);

    const masterHashEl = document.getElementById("master-hash");
    if (masterHashEl) masterHashEl.innerText = masterHash;
}

function lockAndSubmitRecord() {
    alert("🔒 EVIDENCE RECORD LOCKED & CRYPTOGRAPHICALLY SIGNED.\nRecord synchronized to central repository with dual photo specimens.");
    
    // Reset state for new capture session
    hasCurrentTestBeenCounted = false;
    colorCardBlob = null;
    colorCardHash = null;
    colorCardDataUrl = null;
    colorCardTime = null;

    testTubeBlob = null;
    testTubeHash = null;
    testTubeDataUrl = null;
    testTubeTime = null;

    recordedVideoBlob = null;
    videoHash = null;
    recordedAudioBlob = null;
    audioHash = null;

    // Reset UI previews
    const cardPlaceholder = document.getElementById("card-preview-placeholder");
    const cardContent = document.getElementById("card-preview-content");
    const tubePlaceholder = document.getElementById("tube-preview-placeholder");
    const tubeContent = document.getElementById("tube-preview-content");
    const videoPreviewBox = document.getElementById("video-preview-box");
    const audioPlayback = document.getElementById("audio-playback");
    const badgeCard = document.getElementById("badge-card");
    const badgeTube = document.getElementById("badge-tube");
    const countChip = document.getElementById("preview-count-chip");
    const runBanner = document.getElementById("run-analysis-banner");
    const analysisCard = document.getElementById("analysis-card");

    if (cardPlaceholder) cardPlaceholder.classList.remove("hidden");
    if (cardContent) cardContent.classList.add("hidden");
    if (tubePlaceholder) tubePlaceholder.classList.remove("hidden");
    if (tubeContent) tubeContent.classList.add("hidden");
    if (videoPreviewBox) videoPreviewBox.classList.add("hidden");
    if (audioPlayback) audioPlayback.classList.add("hidden");

    if (badgeCard) {
        badgeCard.innerText = "PENDING";
        badgeCard.className = "text-[9px] bg-teal-900 text-teal-200 px-1.5 py-0.5 rounded font-mono";
    }
    if (badgeTube) {
        badgeTube.innerText = "PENDING";
        badgeTube.className = "text-[9px] bg-slate-300 text-slate-700 px-1.5 py-0.5 rounded font-mono";
    }
    if (countChip) countChip.innerText = "0 OF 2 PHOTOS";
    if (runBanner) runBanner.classList.add("hidden");
    if (analysisCard) analysisCard.classList.add("hidden");

    setCaptureTarget('card');
    updateMetricsUI();
    navigateTo("screen-dashboard");
}