
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
    // AI STATE
    // ==========================================================

    property string aiState: "idle"

    // ==========================================================
    // STREAMING STATE
    // ==========================================================

    property int streamStep: 0

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

                spacing: 24

                // ==================================================
                // AI CORE AREA
                // ==================================================

                Item {

                    Layout.fillWidth: true

                    Layout.fillHeight: true

                    Layout.minimumWidth: 600

                    // ----------------------------------------------
                    // CENTER ORB
                    // ----------------------------------------------

                    AIOrb {

                        id: aiOrb

                        anchors.centerIn: parent

                        width: 300

                        height: 390

                        state: window.aiState
                    }

                    // ----------------------------------------------
                    // STATE LABEL
                    // ----------------------------------------------

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

                            case "error":
                                return Theme.danger

                            case "speaking":
                                return Theme.accent

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

                        // ------------------------------------------
                        // STREAMING FINISHED
                        // ------------------------------------------

                        onStreamingFinished: {

                            window.aiState = "idle"
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

            // --------------------------------------------------
            // TOP SEPARATOR
            // --------------------------------------------------

            Rectangle {

                anchors.top: parent.top

                anchors.left: parent.left

                anchors.right: parent.right

                height: 1

                color: Theme.border

                opacity: 0.65
            }

            // --------------------------------------------------
            // COMMAND CENTER
            // --------------------------------------------------

            CommandCenter {

                id: commandCenter

                anchors.centerIn: parent

                width: Math.min(
                    parent.width - 180,
                    760
                )

                height: 72

                state: window.aiState

                onCommandSubmitted: function(command) {

                    // ------------------------------------------
                    // Add user message
                    // ------------------------------------------

                    chatView.addUserMessage(command)

                    // ------------------------------------------
                    // Move AI into thinking state
                    // ------------------------------------------

                    window.aiState = "thinking"

                    // ------------------------------------------
                    // Start temporary response simulation
                    // ------------------------------------------

                    responseTimer.restart()
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
    // TEMPORARY THINKING DELAY
    //
    // This will later be replaced by the Python EventBus.
    // ==========================================================

    Timer {

        id: responseTimer

        interval: 1000

        repeat: false

        onTriggered: {

            // ----------------------------------------------
            // Move AI into speaking mode
            // ----------------------------------------------

            window.aiState = "speaking"

            // ----------------------------------------------
            // Create empty assistant message
            // ----------------------------------------------

            chatView.startStreaming()

            // ----------------------------------------------
            // Reset stream
            // ----------------------------------------------

            window.streamStep = 0

            // ----------------------------------------------
            // Start simulated token stream
            // ----------------------------------------------

            streamTimer.start()
        }
    }

    // ==========================================================
    // TEMPORARY STREAM SIMULATOR
    //
    // Simulates an AI response arriving token-by-token.
    //
    // Later Python will replace this completely.
    // ==========================================================

    Timer {

        id: streamTimer

        interval: 55

        repeat: true

        onTriggered: {

            var chunks = [

                "Command ",
                "received. ",
                "Krakken ",
                "is ",
                "processing ",
                "your ",
                "request."
            ]

            // ----------------------------------------------
            // Send next chunk
            // ----------------------------------------------

            if (
                window.streamStep <
                chunks.length
            ) {

                chatView.appendStreamText(
                    chunks[window.streamStep]
                )

                window.streamStep++

                return
            }

            // ----------------------------------------------
            // Streaming completed
            // ----------------------------------------------

            streamTimer.stop()

            window.streamStep = 0

            chatView.finishStreaming()

            // onStreamingFinished in ChatView
            // returns the AI to idle.
        }
    }

    // ==========================================================
    // WINDOW CLOSE SAFETY
    // ==========================================================

    onClosing: function(close) {

        responseTimer.stop()

        streamTimer.stop()

        close.accepted = true
    }
}

