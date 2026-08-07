
import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Kraken

Item {

    id: root

    // ==========================================================
    // PUBLIC API
    // ==========================================================

    property string state: "idle"

    property string placeholderText: "Ask Krakken anything..."

    signal commandSubmitted(string command)

    // ==========================================================
    // SIZE
    // ==========================================================

    implicitWidth: 620
    implicitHeight: 92

    // ==========================================================
    // STATE COLOR
    // ==========================================================

    property color stateColor: {

        switch (root.state) {

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

    // ==========================================================
    // OUTER GLOW
    // ==========================================================

    Rectangle {

        id: outerGlow

        anchors.fill: commandPanel

        anchors.margins: -5

        radius: Theme.radiusLarge + 5

        color: "transparent"

        border.width: 1

        border.color: root.stateColor

        opacity: 0.18

        Behavior on border.color {

            ColorAnimation {

                duration: Theme.medium
            }
        }

        SequentialAnimation on opacity {

            running: root.state !== "idle"

            loops: Animation.Infinite

            NumberAnimation {

                from: 0.12

                to: 0.32

                duration: 900
            }

            NumberAnimation {

                from: 0.32

                to: 0.12

                duration: 900
            }
        }
    }

    // ==========================================================
    // COMMAND PANEL
    // ==========================================================

    Rectangle {

        id: commandPanel

        anchors.fill: parent

        radius: Theme.radiusLarge

        color: Theme.surface

        border.width: 1

        border.color: root.stateColor

        opacity: 0.97

        Behavior on border.color {

            ColorAnimation {

                duration: Theme.medium
            }
        }

        // ======================================================
        // TOP ACCENT LINE
        // ======================================================

        Rectangle {

            anchors.left: parent.left

            anchors.right: parent.right

            anchors.top: parent.top

            height: 2

            radius: 1

            color: root.stateColor

            opacity: 0.8

            Behavior on color {

                ColorAnimation {

                    duration: Theme.medium
                }
            }
        }

        // ======================================================
        // CONTENT
        // ======================================================

        RowLayout {

            anchors.fill: parent

            anchors.leftMargin: 18

            anchors.rightMargin: 14

            anchors.topMargin: 10

            anchors.bottomMargin: 10

            spacing: 12

            // ==================================================
            // AI INDICATOR
            // ==================================================

            Rectangle {

                Layout.alignment: Qt.AlignVCenter

                width: 42

                height: 42

                radius: 21

                color: root.stateColor

                opacity: 0.15

                border.width: 1

                border.color: root.stateColor

                Behavior on color {

                    ColorAnimation {

                        duration: Theme.medium
                    }
                }

                Text {

                    anchors.centerIn: parent

                    text: "◈"

                    color: root.stateColor

                    font.pixelSize: 20

                    font.bold: true
                }
            }

            // ==================================================
            // INPUT
            // ==================================================

            TextField {

                id: commandInput

                Layout.fillWidth: true

                Layout.fillHeight: true

                placeholderText: root.placeholderText

                placeholderTextColor: Theme.textSecondary

                color: Theme.textPrimary

                font.pixelSize: 16

                selectByMouse: true

                background: Item {}

                verticalAlignment: Text.AlignVCenter

                leftPadding: 0

                rightPadding: 0

                topPadding: 0

                bottomPadding: 0

                onAccepted: {

                    submitCommand()
                }

                Keys.onReturnPressed: {

                    submitCommand()
                }

                Keys.onEnterPressed: {

                    submitCommand()
                }
            }

            // ==================================================
            // MICROPHONE BUTTON
            // ==================================================

            Rectangle {

                id: microphoneButton

                Layout.alignment: Qt.AlignVCenter

                width: 44

                height: 44

                radius: 22

                color: microphoneMouse.containsMouse
                       ? root.stateColor
                       : "transparent"

                border.width: 1

                border.color: root.stateColor

                Behavior on color {

                    ColorAnimation {

                        duration: Theme.fast
                    }
                }

                Text {

                    anchors.centerIn: parent

                    text: "●"

                    color: root.stateColor

                    font.pixelSize: 18
                }

                MouseArea {

                    id: microphoneMouse

                    anchors.fill: parent

                    hoverEnabled: true

                    cursorShape: Qt.PointingHandCursor

                    onClicked: {

                        root.state =
                            root.state === "listening"
                            ? "idle"
                            : "listening"
                    }
                }
            }

            // ==================================================
            // SEND BUTTON
            // ==================================================

            Rectangle {

                id: sendButton

                Layout.alignment: Qt.AlignVCenter

                width: 52

                height: 44

                radius: 14

                color: sendMouse.containsMouse
                       ? Qt.lighter(root.stateColor, 1.15)
                       : root.stateColor

                Behavior on color {

                    ColorAnimation {

                        duration: Theme.fast
                    }
                }

                Text {

                    anchors.centerIn: parent

                    text: "➜"

                    color: Theme.background

                    font.pixelSize: 21

                    font.bold: true
                }

                MouseArea {

                    id: sendMouse

                    anchors.fill: parent

                    hoverEnabled: true

                    cursorShape: Qt.PointingHandCursor

                    onClicked: {

                        submitCommand()
                    }
                }
            }
        }
    }

    // ==========================================================
    // SUBMIT
    // ==========================================================

    function submitCommand() {

        var command = commandInput.text.trim()

        if (command.length === 0)
            return

        root.commandSubmitted(command)

        commandInput.clear()

        root.state = "thinking"
    }

    // ==========================================================
    // FOCUS
    // ==========================================================

    function focusInput() {

        commandInput.forceActiveFocus()
    }

    // ==========================================================
    // STATE TRANSITION
    // ==========================================================

    Behavior on stateColor {

        ColorAnimation {

            duration: Theme.medium
        }
    }
}

