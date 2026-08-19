import QtQuick

import Kraken

Item {

    id: root

    // ==========================================================
    // PUBLIC API
    // ==========================================================

    property string state: "idle"

    property color orbColor: Theme.accent

    property bool animated: true

    property bool showLabel: true

    property bool showParticles: true

    // ==========================================================
    // SIZE
    // ==========================================================

    implicitWidth: 340
    implicitHeight: 390

    // ==========================================================
    // STATE CONFIGURATION
    // ==========================================================

    property real pulseScale: {

        switch (root.state) {

        case "listening":
            return 1.10

        case "thinking":
            return 1.07

        case "speaking":
            return 1.12

        case "processing":
            return 1.09

        case "error":
            return 1.03

        default:
            return 1.035
        }
    }

    property int pulseDuration: {

        switch (root.state) {

        case "listening":
            return 600

        case "thinking":
            return 900

        case "speaking":
            return 420

        case "processing":
            return 700

        case "error":
            return 280

        default:
            return 1500
        }
    }

    property color stateColor: {

        switch (root.state) {

        case "listening":
            return Theme.accentGreen

        case "thinking":
            return Theme.accentPurple

        case "speaking":
            return Theme.accent

        case "processing":
            return Theme.warning

        case "error":
            return Theme.danger

        default:
            return root.orbColor
        }
    }

    // ==========================================================
    // CENTRAL POSITION
    // ==========================================================

    Item {

        id: orbSystem

        anchors.horizontalCenter: parent.horizontalCenter

        anchors.top: parent.top

        width: 300
        height: 300

        // ======================================================
        // AMBIENT GLOW (soft layered halo behind everything)
        // ======================================================

        Item {

            id: glow

            anchors.centerIn: parent

            width: 300
            height: 300

            Repeater {

                model: 4

                delegate: Rectangle {

                    anchors.centerIn: parent

                    width: 190 + index * 34
                    height: width

                    radius: width / 2

                    color: "transparent"

                    border.width: 1

                    border.color: root.stateColor

                    opacity: 0.05 - index * 0.008

                    Behavior on border.color {
                        ColorAnimation { duration: Theme.medium }
                    }
                }
            }
        }

        // ======================================================
        // OUTER ENERGY FIELD
        // ======================================================

        Rectangle {

            id: outerField

            anchors.centerIn: parent

            width: 292
            height: 292

            radius: width / 2

            color: "transparent"

            border.width: 1

            border.color: root.stateColor

            opacity: 0.18

            scale: 1.0

            SequentialAnimation on scale {

                running: root.animated

                loops: Animation.Infinite

                NumberAnimation {

                    from: 0.94
                    to: 1.06

                    duration: root.pulseDuration * 2

                    easing.type: Easing.InOutSine
                }

                NumberAnimation {

                    from: 1.06
                    to: 0.94

                    duration: root.pulseDuration * 2

                    easing.type: Easing.InOutSine
                }
            }

            Behavior on border.color {

                ColorAnimation {

                    duration: Theme.medium
                }
            }
        }

        // ======================================================
        // OUTER ROTATING RING
        // ======================================================

        Item {

            id: outerRing

            anchors.fill: parent

            RotationAnimation on rotation {

                running: root.animated

                loops: Animation.Infinite

                from: 0
                to: 360

                duration: root.state === "thinking"
                           ? 4000
                           : 9000
            }

            Repeater {

                model: 12

                delegate: Rectangle {

                    width: index % 3 === 0 ? 10 : 4

                    height: 2

                    radius: 1

                    color: root.stateColor

                    opacity: index % 3 === 0 ? 0.85 : 0.35

                    x: outerRing.width / 2
                       + Math.cos(index * Math.PI / 6)
                       * 142
                       - width / 2

                    y: outerRing.height / 2
                       + Math.sin(index * Math.PI / 6)
                       * 142
                       - height / 2

                    rotation: index * 30 + 90
                }
            }
        }

        // ======================================================
        // SECOND ROTATING RING
        // ======================================================

        Rectangle {

            id: energyRing

            anchors.centerIn: parent

            width: 242
            height: 242

            radius: width / 2

            color: "transparent"

            border.width: 1

            border.color: root.stateColor

            opacity: 0.45

            RotationAnimation on rotation {

                running: root.animated

                loops: Animation.Infinite

                from: 360
                to: 0

                duration: root.state === "speaking"
                           ? 2600
                           : 7000
            }

            Behavior on border.color {

                ColorAnimation {

                    duration: Theme.medium
                }
            }
        }

        // ======================================================
        // ENERGY PULSES
        // ======================================================

        Rectangle {

            id: pulseRing

            anchors.centerIn: parent

            width: 215
            height: 215

            radius: width / 2

            color: "transparent"

            border.width: 2

            border.color: root.stateColor

            opacity: 0.25

            SequentialAnimation on scale {

                running: root.animated

                loops: Animation.Infinite

                NumberAnimation {

                    from: 0.82
                    to: 1.12

                    duration: root.pulseDuration * 2

                    easing.type: Easing.OutCubic
                }

                NumberAnimation {

                    from: 1.12
                    to: 0.82

                    duration: root.pulseDuration * 2

                    easing.type: Easing.InCubic
                }
            }
        }

        // ======================================================
        // ORBITAL PARTICLES
        // ======================================================

        Repeater {

            model: 8

            delegate: Rectangle {

                id: orbitalParticle

                width: index % 2 === 0 ? 5 : 3

                height: width

                radius: width / 2

                color: root.stateColor

                opacity: 0.8

                property real orbitAngle:
                    index * (360 / 8)

                property real orbitRadius:
                    index % 2 === 0 ? 112 : 92

                x: orbSystem.width / 2
                   + Math.cos(orbitAngle * Math.PI / 180)
                   * orbitRadius
                   - width / 2

                y: orbSystem.height / 2
                   + Math.sin(orbitAngle * Math.PI / 180)
                   * orbitRadius
                   - height / 2

                // subtle soft trail behind each particle
                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width * 2.4
                    height: parent.height * 2.4
                    radius: width / 2
                    color: root.stateColor
                    opacity: 0.18
                }

                SequentialAnimation on orbitAngle {

                    running: root.animated

                    loops: Animation.Infinite

                    NumberAnimation {

                        from: orbitalParticle.orbitAngle

                        to: orbitalParticle.orbitAngle + 360

                        duration: root.state === "thinking"
                                   ? 2800
                                   : 6000

                        easing.type: Easing.Linear
                    }
                }

                Behavior on color {

                    ColorAnimation {

                        duration: Theme.medium
                    }
                }
            }
        }

        // ======================================================
        // MAIN ORB
        // ======================================================

        Rectangle {

            id: orb

            anchors.centerIn: parent

            width: 170
            height: 170

            radius: width / 2

            border.width: 2

            border.color: root.stateColor

            scale: 1.0

            layer.enabled: true

            // Glass-like depth instead of a flat fill
            gradient: Gradient {

                orientation: Gradient.Vertical

                GradientStop { position: 0.0; color: Qt.lighter(Theme.background, 1.35) }
                GradientStop { position: 0.45; color: Theme.background }
                GradientStop { position: 1.0; color: Qt.darker(Theme.background, 1.15) }
            }

            SequentialAnimation on scale {

                running: root.animated

                loops: Animation.Infinite

                NumberAnimation {

                    to: root.pulseScale

                    duration: root.pulseDuration

                    easing.type: Easing.InOutSine
                }

                NumberAnimation {

                    to: 1.0

                    duration: root.pulseDuration

                    easing.type: Easing.InOutSine
                }
            }

            Behavior on border.color {

                ColorAnimation {

                    duration: Theme.medium
                }
            }

            // ==================================================
            // INNER CORE
            // ==================================================

            Rectangle {

                id: core

                anchors.centerIn: parent

                width: 108
                height: 108

                radius: width / 2

                opacity: 0.88

                scale: 1.0

                gradient: Gradient {

                    orientation: Gradient.Vertical

                    GradientStop { position: 0.0; color: Qt.lighter(root.stateColor, 1.25) }
                    GradientStop { position: 1.0; color: Qt.darker(root.stateColor, 1.1) }
                }

                SequentialAnimation on scale {

                    running: root.animated

                    loops: Animation.Infinite

                    NumberAnimation {

                        from: 0.92
                        to: 1.06

                        duration: root.pulseDuration

                        easing.type: Easing.InOutSine
                    }

                    NumberAnimation {

                        from: 1.06
                        to: 0.92

                        duration: root.pulseDuration

                        easing.type: Easing.InOutSine
                    }
                }

                SequentialAnimation on opacity {

                    running: root.animated

                    loops: Animation.Infinite

                    NumberAnimation {

                        from: 0.65
                        to: 1.0

                        duration: root.pulseDuration
                    }

                    NumberAnimation {

                        from: 1.0
                        to: 0.65

                        duration: root.pulseDuration
                    }
                }
            }

            // ==================================================
            // CORE HIGHLIGHT
            // ==================================================

            Rectangle {

                anchors.centerIn: parent

                width: 74
                height: 74

                radius: width / 2

                color: Qt.lighter(
                    root.stateColor,
                    1.12
                )

                opacity: 0.35

                scale: 1.0

                SequentialAnimation on scale {

                    running: root.animated

                    loops: Animation.Infinite

                    NumberAnimation {

                        from: 0.85
                        to: 1.15

                        duration: root.pulseDuration

                    }

                    NumberAnimation {

                        from: 1.15
                        to: 0.85

                        duration: root.pulseDuration

                    }
                }
            }

            // ==================================================
            // SPECULAR HIGHLIGHT (glass sheen, upper-left)
            // ==================================================

            Rectangle {

                width: 56
                height: 30

                radius: height / 2

                x: parent.width * 0.22
                y: parent.height * 0.16

                rotation: -28

                color: "white"

                opacity: 0.10
            }

            // ==================================================
            // AI SYMBOL
            // ==================================================

            Text {

                anchors.centerIn: parent

                text: "AI"

                color: Theme.background

                font.pixelSize: 42

                font.bold: true

                font.letterSpacing: 3

                scale: 1.0

                style: Text.Raised

                styleColor: Qt.rgba(0, 0, 0, 0.25)
            }
        }
    }

    // ==========================================================
    // STATE LABEL
    // ==========================================================

    Rectangle {

        id: labelChip

        visible: root.showLabel

        anchors.horizontalCenter: parent.horizontalCenter

        anchors.top: orbSystem.bottom

        anchors.topMargin: Theme.spacingL

        width: stateLabel.implicitWidth + 24
        height: stateLabel.implicitHeight + 10

        radius: height / 2

        color: root.stateColor

        opacity: 0.10

        border.width: 1

        border.color: root.stateColor

        Behavior on color {
            ColorAnimation { duration: Theme.medium }
        }

        Behavior on border.color {
            ColorAnimation { duration: Theme.medium }
        }

        Text {

            id: stateLabel

            anchors.centerIn: parent

            text: {

                switch (root.state) {

                case "listening":
                    return "LISTENING"

                case "thinking":
                    return "THINKING"

                case "speaking":
                    return "SPEAKING"

                case "processing":
                    return "PROCESSING"

                case "error":
                    return "SYSTEM ERROR"

                default:
                    return "READY"
                }
            }

            color: root.stateColor

            font.pixelSize: Theme.fontSmall

            font.bold: true

            font.letterSpacing: 3

            opacity: 1.0

            Behavior on color {

                ColorAnimation {

                    duration: Theme.medium
                }
            }
        }
    }

    // ==========================================================
    // STATE INDICATOR
    // ==========================================================

    Rectangle {

        visible: root.showLabel

        anchors.horizontalCenter: parent.horizontalCenter

        anchors.top: parent.top

        anchors.topMargin: 306

        width: 6
        height: 6

        radius: 3

        color: root.stateColor

        opacity: 0.9

        SequentialAnimation on opacity {

            running: root.animated

            loops: Animation.Infinite

            NumberAnimation {

                from: 0.35
                to: 1.0

                duration: root.pulseDuration
            }

            NumberAnimation {

                from: 1.0
                to: 0.35

                duration: root.pulseDuration
            }
        }
    }

    // ==========================================================
    // STATE COLOR TRANSITION
    // ==========================================================

    Behavior on stateColor {

        ColorAnimation {

            duration: Theme.medium

            easing.type: Easing.InOutCubic
        }
    }
}
