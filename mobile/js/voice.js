/**
 * Voice.js - Sesli Kanal ve WebRTC Yönetimi
 * Gelişmiş Mobil Deneyimi ve Premium Visualizer Desteği
 */

(function() {
    'use strict';

    // Global Ses Durumu
    const VoiceState = {
        isMuted: false,
        isDeafened: false,
        localStream: null,
        audioCtx: null,
        analyser: null,
        dataArray: null,
        animationId: null,
        peers: {},
        currentChannelId: null
    };

    // DOM Elementleri
    function drawRoundedRectCompat(ctx, x, y, w, h, r) {
        if (!ctx) return;
        if (typeof ctx.roundRect === 'function') {
            ctx.beginPath();
            ctx.roundRect(x, y, w, h, r);
            return;
        }
        const rr = Math.max(0, Math.min(r || 0, Math.min(w, h) / 2));
        ctx.beginPath();
        ctx.moveTo(x + rr, y);
        ctx.arcTo(x + w, y, x + w, y + h, rr);
        ctx.arcTo(x + w, y + h, x, y + h, rr);
        ctx.arcTo(x, y + h, x, y, rr);
        ctx.arcTo(x, y, x + w, y, rr);
        ctx.closePath();
    }

    const elements = {
        muteBtn: document.getElementById('muteBtn'),
        deafenBtn: document.getElementById('deafenBtn'),
        disconnectBtn: document.getElementById('disconnectBtn'),
        visualizer: document.getElementById('voiceVisualizer'),
        userList: document.getElementById('voiceUserList')
    };

    /**
     * Ses Görselleştiriciyi Başlat (Canvas API)
     */
    function initVisualizer() {
        if (!elements.visualizer || !VoiceState.localStream) return;

        if (!VoiceState.audioCtx) {
            VoiceState.audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            VoiceState.analyser = VoiceState.audioCtx.createAnalyser();
            const source = VoiceState.audioCtx.createMediaStreamSource(VoiceState.localStream);
            source.connect(VoiceState.analyser);
            VoiceState.analyser.fftSize = 64;
            const bufferLength = VoiceState.analyser.frequencyBinCount;
            VoiceState.dataArray = new Uint8Array(bufferLength);
        }

        const canvas = elements.visualizer;
        const dpr = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
        const rect = canvas.getBoundingClientRect();
        if (rect.width && rect.height) {
            canvas.width = Math.round(rect.width * dpr);
            canvas.height = Math.round(rect.height * dpr);
        }
        const ctx = canvas.getContext('2d');
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        const width = rect.width || canvas.width;
        const height = rect.height || canvas.height;

        function draw() {
            VoiceState.animationId = requestAnimationFrame(draw);
            VoiceState.analyser.getByteFrequencyData(VoiceState.dataArray);

            ctx.clearRect(0, 0, width, height);
            
            // Premium Gradient Efekti
            const gradient = ctx.createLinearGradient(0, 0, width, 0);
            gradient.addColorStop(0, 'rgba(99, 102, 241, 0.2)');
            gradient.addColorStop(0.5, 'rgba(129, 140, 248, 0.8)');
            gradient.addColorStop(1, 'rgba(99, 102, 241, 0.2)');

            const barWidth = (width / VoiceState.dataArray.length) * 2.5;
            let x = 0;

            for (let i = 0; i < VoiceState.dataArray.length; i++) {
                const barHeight = (VoiceState.dataArray[i] / 255) * height;
                
                ctx.fillStyle = gradient;
                // Oval çubuk çizimi
                const radius = barWidth / 2;
                const y = (height - barHeight) / 2;
                
                drawRoundedRectCompat(ctx, x, y, barWidth - 2, barHeight, 5);
                ctx.fill();

                x += barWidth + 1;
            }
        }

        draw();
    }

    /**
     * Mikrofonu Aç/Kapat
     */
    function toggleMute() {
        if (!VoiceState.localStream) return;

        VoiceState.isMuted = !VoiceState.isMuted;
        VoiceState.localStream.getAudioTracks().forEach(track => {
            track.enabled = !VoiceState.isMuted;
        });

        // UI Güncelleme
        if (VoiceState.isMuted) {
            elements.muteBtn.classList.add('active');
            elements.muteBtn.innerHTML = '<i class="fa-solid fa-microphone-slash"></i>';
            showToast("Mikrofon kapatıldı");
        } else {
            elements.muteBtn.classList.remove('active');
            elements.muteBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
            showToast("Mikrofon açıldı");
        }
    }

    /**
     * Sesi (Kulaklığı) Aç/Kapat
     */
    function toggleDeafen() {
        VoiceState.isDeafened = !VoiceState.isDeafened;
        
        // Tüm uzak ses tracklerini sustur
        const remoteAudios = document.querySelectorAll('.remote-audio');
        remoteAudios.forEach(audio => {
            audio.muted = VoiceState.isDeafened;
        });

        // UI Güncelleme
        if (VoiceState.isDeafened) {
            elements.deafenBtn.classList.add('active');
            elements.deafenBtn.innerHTML = '<i class="fa-solid fa-volume-xmark"></i>';
            if (!VoiceState.isMuted) toggleMute(); // Sağırlaşan kişi otomatik mute olur
            showToast("Sesler susturuldu");
        } else {
            elements.deafenBtn.classList.remove('active');
            elements.deafenBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
            showToast("Sesler açıldı");
        }
    }

    /**
     * Kanaldan Ayrıl
     */
    function disconnect() {
        if (VoiceState.animationId) cancelAnimationFrame(VoiceState.animationId);
        
        if (VoiceState.localStream) {
            VoiceState.localStream.getTracks().forEach(track => track.stop());
        }

        if (VoiceState.audioCtx) {
            VoiceState.audioCtx.close();
        }

        showToast("Bağlantı kesildi");
        
        // Sunucuya ayrılma bilgisini gönder ve ana sayfaya dön
        setTimeout(() => {
            window.location.href = document.referrer || '/';
        }, 500);
    }

    /**
     * Medya İzinlerini Al ve Başlat
     */
    async function startVoice() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }, 
                video: false 
            });
            
            VoiceState.localStream = stream;
            initVisualizer();
            showToast("Ses bağlantısı başarılı");

        } catch (err) {
            console.error("Mikrofon erişim hatası:", err);
            showToast("Mikrofon izni reddedildi!", "error");
        }
    }

    /**
     * Basit Toast Bildirimi (App.js ile uyumlu)
     */
    function showToast(message, type = "info") {
        if (window.MobileApp && window.MobileApp.showNotification) {
            window.MobileApp.showNotification(message, type);
        } else {
            console.log(`[Voice] ${type.toUpperCase()}: ${message}`);
        }
    }

    function resumeAudioContext() {
        if (VoiceState.audioCtx && VoiceState.audioCtx.state === 'suspended') {
            VoiceState.audioCtx.resume().catch(() => {});
        }
    }

    // Event Listeners
    if (elements.muteBtn) elements.muteBtn.addEventListener('click', function(){ resumeAudioContext(); toggleMute(); });
    if (elements.deafenBtn) elements.deafenBtn.addEventListener('click', function(){ resumeAudioContext(); toggleDeafen(); });
    if (elements.disconnectBtn) elements.disconnectBtn.addEventListener('click', disconnect);

    // Başlat
    document.addEventListener('DOMContentLoaded', () => {
        // Kanal ID'sini URL'den veya data attribute'dan al
        const pathParts = window.location.pathname.split('/');
        VoiceState.currentChannelId = pathParts[pathParts.length - 1];
        
        startVoice();
    });

    // Sayfa değiştirilirken temizlik yap
    window.addEventListener('beforeunload', () => {
        if (VoiceState.localStream) {
            VoiceState.localStream.getTracks().forEach(track => track.stop());
        }
    });

})();