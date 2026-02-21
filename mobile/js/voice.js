(function () {
  const root = document.getElementById("voicepage");
  if (!root) return;

  const serverId = root.getAttribute("data-server");
  const channelId = root.getAttribute("data-channel");
  const me = Number(root.getAttribute("data-me") || "0");
  const joinBtn = document.getElementById("voicejoin");
  const muteBtn = document.getElementById("voicemute");
  const usersBox = document.getElementById("voiceusers");
  const audios = document.getElementById("audios");

  let stream = null;
  let source = null;
  let refreshTimer = null;
  let lastSignal = 0;
  const peers = new Map();
  let muted = false;
  let joined = false;

  function iceConfig() {
    return { iceServers: [{ urls: "stun:stun.l.google.com:19302" }] };
  }

  async function postSignal(target, kind, payload) {
    const fd = new FormData();
    fd.append("target", String(target));
    fd.append("kind", kind);
    fd.append("payload", payload);
    await fetch(`/voice/signal/${serverId}/${channelId}`, {
      method: "POST",
      body: fd,
      headers: { "X-Requested-With": "fetch" },
    });
  }

  function ensurePeer(remoteId) {
    if (peers.has(remoteId)) return peers.get(remoteId);
    const pc = new RTCPeerConnection(iceConfig());
    if (stream) {
      stream.getTracks().forEach((t) => pc.addTrack(t, stream));
    }
    pc.onicecandidate = (e) => {
      if (e.candidate) postSignal(remoteId, "candidate", JSON.stringify(e.candidate)).catch(() => {});
    };
    pc.ontrack = (e) => {
      const id = `audio-${remoteId}`;
      let el = document.getElementById(id);
      if (!el) {
        el = document.createElement("audio");
        el.id = id;
        el.autoplay = true;
        el.controls = true;
        audios.appendChild(el);
      }
      el.srcObject = e.streams[0];
      const p = el.play();
      if (p && typeof p.catch === "function") p.catch(() => {});
    };
    peers.set(remoteId, pc);
    return pc;
  }

  function syncLocalTracksToPeers() {
    if (!stream) return;
    const tracks = stream.getAudioTracks();
    peers.forEach((pc) => {
      tracks.forEach((track) => {
        const sender = pc.getSenders().find((s) => s.track && s.track.kind === track.kind);
        if (sender) sender.replaceTrack(track);
        else pc.addTrack(track, stream);
      });
    });
  }

  async function makeOffer(remoteId) {
    const pc = ensurePeer(remoteId);
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await postSignal(remoteId, "offer", JSON.stringify(offer));
  }

  async function handleSignal(msg) {
    if (!msg || !msg.kind || msg.kind === "ping") return;
    const sender = Number(msg.sender || 0);
    if (!sender || sender === me) return;
    const pc = ensurePeer(sender);
    if (msg.kind === "hello") {
      await makeOffer(sender);
      return;
    }
    if (msg.kind === "offer") {
      const offer = JSON.parse(msg.payload || "{}");
      await pc.setRemoteDescription(new RTCSessionDescription(offer));
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      await postSignal(sender, "answer", JSON.stringify(answer));
      return;
    }
    if (msg.kind === "answer") {
      const answer = JSON.parse(msg.payload || "{}");
      await pc.setRemoteDescription(new RTCSessionDescription(answer));
      return;
    }
    if (msg.kind === "candidate") {
      const cand = JSON.parse(msg.payload || "{}");
      if (cand && cand.candidate) await pc.addIceCandidate(new RTCIceCandidate(cand));
    }
  }

  function startSignalStream() {
    if (source) source.close();
    source = new EventSource(`/voice/stream/${serverId}/${channelId}?last=${lastSignal}`);
    source.onmessage = async (evt) => {
      try {
        const data = JSON.parse(evt.data || "{}");
        if (data.id) lastSignal = Math.max(lastSignal, Number(data.id));
        await handleSignal(data);
      } catch (_) {}
    };
    source.onerror = () => {
      if (source) source.close();
      source = null;
      setTimeout(startSignalStream, 2000);
    };
  }

  async function refreshUsers() {
    const res = await fetch(`/voice/ping/${serverId}/${channelId}`, {
      method: "POST",
      headers: { "X-Requested-With": "fetch" },
    });
    const data = await res.json();
    if (!data.ok) return;
    usersBox.innerHTML = "";
    (data.users || []).forEach((u) => {
      const row = document.createElement("div");
      row.className = "cardrow";
      row.innerHTML = `<div class="who"><img src="${u.avatar}" class="avatar sm"> ${u.username}</div>`;
      usersBox.appendChild(row);
    });
  }

  async function joinVoice() {
    if (!stream) {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    }
    syncLocalTracksToPeers();
    await refreshUsers();
    startSignalStream();
    await postSignal(0, "hello", "{}");
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => refreshUsers().catch(() => {}), 12000);
    joined = true;
    joinBtn.innerHTML = '<i class="fa-solid fa-phone-slash"></i> Kanaldan Ayril';
  }

  function leaveVoice() {
    joined = false;
    if (refreshTimer) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
    if (source) {
      source.close();
      source = null;
    }
    peers.forEach((pc) => {
      try {
        pc.close();
      } catch (_) {}
    });
    peers.clear();
    if (stream) {
      stream.getTracks().forEach((t) => t.stop());
      stream = null;
    }
    if (audios) audios.innerHTML = "";
    muted = false;
    joinBtn.innerHTML = '<i class="fa-solid fa-phone-volume"></i> Kanala Baglan';
    muteBtn.innerHTML = '<i class="fa-solid fa-microphone-slash"></i> Sustur';
  }

  joinBtn?.addEventListener("click", () => {
    if (joined) {
      leaveVoice();
      return;
    }
    joinVoice().catch(() => {
      alert("Mikrofon erisimi veya ses baglantisi baslatilamadi.");
    });
  });

  muteBtn?.addEventListener("click", () => {
    if (!stream) return;
    muted = !muted;
    stream.getAudioTracks().forEach((t) => (t.enabled = !muted));
    muteBtn.innerHTML = muted
      ? '<i class="fa-solid fa-microphone"></i> Sesi Ac'
      : '<i class="fa-solid fa-microphone-slash"></i> Sustur';
  });
})();
