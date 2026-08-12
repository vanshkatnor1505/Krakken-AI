import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

import Kraken

ApplicationWindow {

    id: window

    visible: true

    width: 1600
    height: 900

    minimumWidth: 1200
    minimumHeight: 700

    title: "Krakken AI"

    color: Theme.background


    // ==========================================================
    // PYTHON BRIDGE
    // ==========================================================

    // IMPORTANT:
    //
    // Python exposes:
    //
    //     krakkenBridge
    //
    // We keep a separate local property so every child receives
    // exactly the same Python object.

    property var bridge: krakkenBridge


    // ==========================================================
    // AI STATE
    // ==========================================================

    property string aiState: "idle"


    // ==========================================================
    // AMBIENT BACKGROUND
    // ==========================================================

    AmbientBackground {

        id: ambientBackground

        anchors.fill: parent

        z: 0

        state: window.aiState

        intensity: 1.0
    }


    // ==========================================================
    // APPLICATION LAYOUT
    // ==========================================================

    ColumnLayout {

        anchors.fill: parent

        spacing: 0

        z: 10


        // ======================================================
        // TOP BAR
        // ======================================================

        TopBar {

            Layout.fillWidth: true

            Layout.preferredHeight: 60
        }


        // ======================================================
        // MAIN AREA
        // ======================================================

        RowLayout {

            Layout.fillWidth: true

            Layout.fillHeight: true

            spacing: 0


            // ==================================================
            // SIDEBAR
            // ==================================================

            Sidebar {

                Layout.fillHeight: true

                Layout.preferredWidth: 90
            }


            // ==================================================
            // CENTER + CHAT
            // ==================================================

            RowLayout {

                Layout.fillWidth: true

                Layout.fillHeight: true

                spacing: 18


                // ==================================================
                // AI CORE
                // ==================================================

                Item {

                    Layout.fillWidth: true

                    Layout.fillHeight: true

                    Layout.minimumWidth: 600


                    AIOrb {

                        id: aiOrb

                        anchors.centerIn: parent

                        width: 300

                        height: 390

                        state: window.aiState
                    }


                    Text {

                        anchors.horizontalCenter:
                            aiOrb.horizontalCenter

                        anchors.top:
                            aiOrb.bottom

                        anchors.topMargin: 8


                        text: {

                            switch (window.aiState) {

                            case "listening":
                                return "LISTENING"

                            case "thinking":
                                return "THINKING"

                            case "processing":
                                return "PROCESSING"

                            case "speaking":
                                return "SPEAKING"

                            case "error":
                                return "SYSTEM ERROR"

                            default:
                                return "SYSTEM READY"
                            }
                        }


                        color: {

                            switch (window.aiState) {

                            case "listening":
                                return Theme.accentGreen

                            case "thinking":
                                return Theme.accentPurple

                            case "processing":
                                return Theme.warning

                            case "speaking":
                                return Theme.accent

                            case "error":
                                return Theme.danger

                            default:
                                return Theme.accent
                            }
                        }


                        font.pixelSize: 11

                        font.bold: true

                        font.letterSpacing: 3

                        opacity: 0.8
                    }
                }


                // ==================================================
                // CHAT PANEL
                // ==================================================

                Item {

                    Layout.fillHeight: true

                    Layout.preferredWidth: 520

                    Layout.minimumWidth: 420

                    Layout.maximumWidth: 560


                    ChatView {

                        id: chatView

                        anchors.fill: parent

                        anchors.topMargin: 28

                        anchors.bottomMargin: 28

                        state: window.aiState

                        // IMPORTANT:
                        //
                        // Do NOT use:
                        //
                        //     assistantBridge: assistantBridge
                        //
                        // because that can resolve to ChatView's
                        // own property.
                        //
                        // Explicitly use the ApplicationWindow
                        // bridge property.

                        assistantBridge: window.bridge


                        onClearRequested: {

                            if (window.bridge) {

                                window.bridge
                                    .clearConversation()
                            }
                        }
                    }
                }
            }
        }


        // ======================================================
        // COMMAND DOCK
        // ======================================================

        Item {

            Layout.fillWidth: true

            Layout.preferredHeight: 108


            Rectangle {

                anchors.top: parent.top

                anchors.left: parent.left

                anchors.right: parent.right

                height: 1

                color: Theme.border

                opacity: 0.65
            }


            CommandCenter {

                id: commandCenter

                anchors.centerIn: parent

                width:
                    Math.min(
                        parent.width - 180,
                        760
                    )

                height: 72

                state: window.aiState


                // ==================================================
                // COMMAND SUBMITTED
                // ==================================================

                onCommandSubmitted: function(command) {

                    if (
                        !command ||
                        command.trim().length === 0
                    ) {
                        return
                    }


                    var cleanCommand =
                        command.trim()


                    // ------------------------------------------------
                    // Add the user message exactly ONCE.
                    // ------------------------------------------------

                    chatView.addUserMessage(
                        cleanCommand
                    )


                    // ------------------------------------------------
                    // Send to Python exactly ONCE.
                    //
                    // ChatView no longer sends messages itself.
                    // ------------------------------------------------

                    if (window.bridge) {

                        console.log(
                            "MAIN: Sending command to AssistantBridge:",
                            cleanCommand
                        )

                        window.bridge.sendMessage(
                            cleanCommand
                        )

                    } else {

                        console.error(
                            "MAIN: krakkenBridge is not available."
                        )

                        chatView.addAssistantMessage(
                            "Error: AssistantBridge is not available."
                        )

                        window.aiState =
                            "error"
                    }
                }
            }
        }


        // ======================================================
        // STATUS BAR
        // ======================================================

        StatusBar {

            Layout.fillWidth: true

            Layout.preferredHeight: 42
        }
    }


    // ==========================================================
    // SINGLE ASSISTANT BRIDGE CONNECTION
    // ==========================================================

    Connections {

        id: bridgeConnections

        target: window.bridge


        // ======================================================
        // STATE
        // ======================================================

        function onStateChanged(state) {

            if (
                state === undefined ||
                state === null
            ) {
                return
            }


            var nextState =
                String(state).trim()


            if (
                nextState.length === 0
            ) {
                return
            }


            console.log(
                "QML AI STATE:",
                nextState
            )


            window.aiState =
                nextState

            chatView.state =
                nextState
        }


        // ======================================================
        // RESPONSE STARTED
        // ======================================================

        function onResponseStarted() {

            console.log(
                "QML RESPONSE STARTED"
            )


            chatView.startStreaming()
        }


        // ======================================================
        // RESPONSE CHUNK
        // ======================================================

        function onResponseChunk(chunk) {

            if (
                chunk === undefined ||
                chunk === null
            ) {
                return
            }


            var text =
                String(chunk)


            if (
                text.length === 0
            ) {
                return
            }


            chatView.appendStreamText(
                text
            )
        }


        // ======================================================
        // RESPONSE FINISHED
        // ======================================================

        function onResponseFinished() {

            console.log(
                "QML RESPONSE FINISHED"
            )


            chatView.finishStreaming()
        }


        // ======================================================
        // ERROR
        // ======================================================

        function onErrorOccurred(errorMessage) {

            console.error(
                "KRAKKEN ERROR:",
                errorMessage
            )


            chatView.cancelStreaming()


            var message =
                errorMessage !== undefined &&
                errorMessage !== null
                ? String(errorMessage)
                : "Unknown assistant error."


            chatView.addAssistantMessage(
                "Error: " + message
            )


            window.aiState =
                "error"
        }


        // ======================================================
        // HISTORY CLEARED
        // ======================================================

        function onHistoryCleared() {

            console.log(
                "QML HISTORY CLEARED"
            )


            chatView.clearMessages()
        }
    }


    // ==========================================================
    // STARTUP
    // ==========================================================

    Component.onCompleted: {

        console.log(
            "========================================"
        )

        console.log(
            "KRAKKEN MAIN WINDOW INITIALIZED"
        )

        console.log(
            "Python bridge:",
            window.bridge
        )

        console.log(
            "ChatView bridge:",
            chatView.assistantBridge
        )

        console.log(
            "========================================"
        )


        if (!window.bridge) {

            console.error(
                "MAIN: krakkenBridge is NULL."
            )

        } else {

            console.log(
                "MAIN: krakkenBridge connected successfully."
            )
        }
    }
}