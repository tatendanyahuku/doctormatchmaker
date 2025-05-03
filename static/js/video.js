const socket = io();

let localStream;
let remoteStream;
let peerConnection;
let currentUser;
let userRole;
let consultationId;
let pollingIntervalId;

const configuration = {
    iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
    ],
};

const localVideo = document.getElementById('localVideo');
const remoteVideo = document.getElementById('remoteVideo');

const startCallBtn = document.getElementById('startCall');
const joinCallBtn = document.getElementById('joinCall');

if (startCallBtn) {
    startCallBtn.onclick = startCall;
}
if (joinCallBtn) {
    joinCallBtn.onclick = joinCall;
}

document.addEventListener("DOMContentLoaded", async function () {
    currentUser = document.getElementById("currentUser").value;
    userRole = document.getElementById("userRole").value;
    consultationId = document.getElementById("consultationId").value;

    await initializeMedia();

    peerConnection = new RTCPeerConnection(configuration);

    peerConnection.onicecandidate = event => {
        if (event.candidate) {
            socket.emit('ice-candidate', event.candidate);
        }
    };

    peerConnection.ontrack = event => {
        if (!remoteStream) {
            remoteStream = new MediaStream();
            remoteVideo.srcObject = remoteStream;
        }
        remoteStream.addTrack(event.track);
    };

    localStream.getTracks().forEach(track => {
        peerConnection.addTrack(track, localStream);
    });

    startSignalingPolling();

    if (userRole === "doctor") {
        await createOffer();
    }

    const startCallBtn = document.getElementById("start-call-btn");

    if (startCallBtn) {
        startCallBtn.addEventListener("click", async () => {
            const consultationRoom = document.getElementById("consultation-room");
            const consultationId = consultationRoom.getAttribute("data-consultation-id");
            const userId = consultationRoom.getAttribute("data-user-id");

            try {
                const response = await fetch(`/api/consultation/${consultationId}/start-call`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ caller_id: userId })
                });

                if (response.ok) {
                    console.log("Call started successfully");
                    alert("Call has been initiated. Waiting for the patient to join.");
                } else {
                    console.error("Failed to start call", await response.json());
                    alert("Failed to start the call. Please try again.");
                }
            } catch (error) {
                console.error("Error starting call", error);
                alert("An error occurred while starting the call.");
            }
        });
    }
});

async function initializeMedia() {
    try {
        localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
        localVideo.srcObject = localStream;
    } catch (error) {
        console.error("Error accessing media devices:", error);
    }
}

async function createOffer() {
    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);
    socket.emit('offer', peerConnection.localDescription);
}

async function createAnswer(offer) {
    await peerConnection.setRemoteDescription(new RTCSessionDescription(offer));
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);
    socket.emit('answer', peerConnection.localDescription);
}

socket.on('offer', offer => {
    peerConnection.setRemoteDescription(new RTCSessionDescription(offer)).then(() => {
        return peerConnection.createAnswer();
    }).then(answer => {
        return peerConnection.setLocalDescription(answer);
    }).then(() => {
        socket.emit('answer', peerConnection.localDescription);
    });
});

socket.on('answer', answer => {
    peerConnection.setRemoteDescription(new RTCSessionDescription(answer));
});

socket.on('ice-candidate', candidate => {
    peerConnection.addIceCandidate(new RTCIceCandidate(candidate));
});

async function sendSignalingData(data) {
    await fetch(`/consultation/api/signaling/${consultationId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            sender: currentUser,
            receiver: userRole === "doctor" ? "patient" : "doctor",
            type: data.type,
            data: JSON.stringify(data.sdp || data.candidate),
        }),
    });
}

function startSignalingPolling() {
    pollingIntervalId = setInterval(async () => {
        const response = await fetch(`/consultation/api/signaling/${consultationId}/${currentUser}`);
        const messages = await response.json();

        for (const msg of messages) {
            const parsedData = JSON.parse(msg.data);

            switch (msg.type) {
                case "offer":
                    await createAnswer(parsedData);
                    break;

                case "answer":
                    await peerConnection.setRemoteDescription(new RTCSessionDescription(parsedData));
                    break;

                case "ice-candidate":
                    await peerConnection.addIceCandidate(new RTCIceCandidate(parsedData));
                    break;
            }
        }
    }, 2000);
}

function startCall() {
    navigator.mediaDevices.getUserMedia({ video: true, audio: true }).then(stream => {
        localStream = stream;
        localVideo.srcObject = stream;

        peerConnection = new RTCPeerConnection(configuration);
        stream.getTracks().forEach(track => peerConnection.addTrack(track, stream));

        peerConnection.ontrack = event => {
            if (!remoteStream) {
                remoteStream = new MediaStream();
                remoteVideo.srcObject = remoteStream;
            }
            remoteStream.addTrack(event.track);
        };

        peerConnection.onicecandidate = event => {
            if (event.candidate) {
                socket.emit('ice-candidate', event.candidate);
            }
        };

        peerConnection.createOffer().then(offer => {
            return peerConnection.setLocalDescription(offer);
        }).then(() => {
            socket.emit('offer', peerConnection.localDescription);
        });
    });
}

function joinCall() {
    navigator.mediaDevices.getUserMedia({ video: true, audio: true }).then(stream => {
        localStream = stream;
        localVideo.srcObject = stream;

        peerConnection = new RTCPeerConnection(configuration);
        stream.getTracks().forEach(track => peerConnection.addTrack(track, stream));

        peerConnection.ontrack = event => {
            if (!remoteStream) {
                remoteStream = new MediaStream();
                remoteVideo.srcObject = remoteStream;
            }
            remoteStream.addTrack(event.track);
        };

        peerConnection.onicecandidate = event => {
            if (event.candidate) {
                socket.emit('ice-candidate', event.candidate);
            }
        };
    });
}
