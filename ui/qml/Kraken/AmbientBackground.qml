
import QtQuick

import Kraken

Item {

    id: root

    anchors.fill: parent

    // ==========================================================
    // PUBLIC API
    // ==========================================================

    property string state: "idle"

    property bool animated: true

    property real intensity: 1.0

    // ==========================================================
    // STATE COLORS
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
    // STATE SPEED
    // ==========================================================

    property real animationSpeed: {

        switch (root.state) {

        case "listening":
            return 0.70

        case "thinking":
            return 0.45

        case "processing":
            return 0.55

        case "speaking":
            return 0.35

        case "error":
            return 0.20

        default:
            return 1.0
        }
    }

    // ==========================================================
    // STATE INTENSITY
    // ==========================================================

    property real stateIntensity: {

        switch (root.state) {

        case "listening":
            return 1.35

        case "thinking":
            return 1.55

        case "processing":
            return 1.45

        case "speaking":
            return 1.70

        case "error":
            return 1.90

        default:
            return 0.75
        }
    }

    // ==========================================================
    // BASE
    // ==========================================================

    Rectangle {

        anchors.fill: parent

        color: "#050812"
    }

    // ==========================================================
    // PRIMARY ATMOSPHERE
    // ==========================================================

    Rectangle {

        id: primaryAura

        width: Math.max(root.width * 0.72, 750)

        height: width

        x: root.width * 0.12

        y: root.height * 0.02

        radius: width / 2

        color: root.stateColor

        opacity: 0.075 * root.intensity * root.stateIntensity

        scale: 1.0

        Behavior on color {

            ColorAnimation {

                duration: Theme.slow

                easing.type: Easing.InOutCubic
            }
        }

        Behavior on opacity {

            NumberAnimation {

                duration: Theme.medium

                easing.type: Easing.InOutSine
            }
        }

        SequentialAnimation on scale {

            running: root.animated

            loops: Animation.Infinite

            NumberAnimation {

                from: 0.90

                to: 1.10

                duration: 7000 * root.animationSpeed

                easing.type: Easing.InOutSine
            }

            NumberAnimation {

                from: 1.10

                to: 0.90

                duration: 7000 * root.animationSpeed

                easing.type: Easing.InOutSine
            }
        }
    }

    // ==========================================================
    // SECONDARY ATMOSPHERE
    // ==========================================================

    Rectangle {

        id: secondaryAura

        width: Math.max(root.width * 0.60, 650)

        height: width

        x: root.width * 0.52

        y: root.height * 0.32

        radius: width / 2

        color: root.stateColor

        opacity: 0.055 * root.intensity * root.stateIntensity

        scale: 1.0

        Behavior on color {

            ColorAnimation {

                duration: Theme.slow

                easing.type: Easing.InOutCubic
            }
        }

        Behavior on opacity {

            NumberAnimation {

                duration: Theme.medium

                easing.type: Easing.InOutSine
            }
        }

        SequentialAnimation on scale {

            running: root.animated

            loops: Animation.Infinite

            NumberAnimation {

                from: 1.08

                to: 0.88

                duration: 9000 * root.animationSpeed

                easing.type: Easing.InOutSine
            }

            NumberAnimation {

                from: 0.88

                to: 1.08

                duration: 9000 * root.animationSpeed

                easing.type: Easing.InOutSine
            }
        }
    }

    // ==========================================================
    // CENTRAL ENERGY
    // ==========================================================

    Rectangle {

        id: centerEnergy

        width: Math.min(root.width, root.height) * 0.70

        height: width

        anchors.centerIn: parent

        radius: width / 2

        color: root.stateColor

        opacity: 0.035 * root.intensity * root.stateIntensity

        scale: 1.0

        Behavior on color {

            ColorAnimation {

                duration: Theme.medium
            }
        }

        SequentialAnimation on scale {

            running: root.animated

            loops: Animation.Infinite

            NumberAnimation {

                from: 0.84

                to: 1.16

                duration: 5000 * root.animationSpeed

                easing.type: Easing.InOutSine
            }

            NumberAnimation {

                from: 1.16

                to: 0.84

                duration: 5000 * root.animationSpeed

                easing.type: Easing.InOutSine
            }
        }
    }

    // ==========================================================
    // TECH GRID
    // ==========================================================

    Item {

        anchors.fill: parent

        opacity: root.state === "thinking"
                 ? 0.20
                 : root.state === "processing"
                   ? 0.17
                   : 0.10

        Behavior on opacity {

            NumberAnimation {

                duration: Theme.medium
            }
        }

        Repeater {

            model: Math.ceil(root.width / 50)

            delegate: Rectangle {

                x: index * 50

                y: 0

                width: 1

                height: root.height

                color: root.stateColor

                opacity: 0.30

                Behavior on color {

                    ColorAnimation {

                        duration: Theme.medium
                    }
                }
            }
        }

        Repeater {

            model: Math.ceil(root.height / 50)

            delegate: Rectangle {

                x: 0

                y: index * 50

                width: root.width

                height: 1

                color: root.stateColor

                opacity: 0.30
            }
        }
    }

    // ==========================================================
    // FLOATING PARTICLES
    // ==========================================================

    Repeater {

        model: 40

        delegate: Rectangle {

            id: particle

            property real originX:
                ((index * 137) % 1000) / 1000

            property real originY:
                ((index * 251) % 1000) / 1000

            property real driftX:
                ((index * 73) % 160) - 80

            property real driftY:
                ((index * 97) % 160) - 80

            width: index % 4 === 0 ? 4 : 2

            height: width

            radius: width / 2

            x: particle.originX * root.width

            y: particle.originY * root.height

            color: root.stateColor

            opacity: 0.25 * root.stateIntensity

            Behavior on color {

                ColorAnimation {

                    duration: Theme.medium
                }
            }

            SequentialAnimation {

                running: root.animated

                loops: Animation.Infinite

                ParallelAnimation {

                    NumberAnimation {

                        target: particle

                        property: "x"

                        to: particle.x + particle.driftX

                        duration:
                            (3500 + index * 100)
                            * root.animationSpeed

                        easing.type: Easing.InOutSine
                    }

                    NumberAnimation {

                        target: particle

                        property: "y"

                        to: particle.y + particle.driftY

                        duration:
                            (3500 + index * 100)
                            * root.animationSpeed

                        easing.type: Easing.InOutSine
                    }

                    NumberAnimation {

                        target: particle

                        property: "opacity"

                        from: 0.08

                        to: 0.75 * root.stateIntensity

                        duration:
                            1800 * root.animationSpeed

                        easing.type: Easing.InOutSine
                    }
                }

                NumberAnimation {

                    target: particle

                    property: "opacity"

                    from: 0.75 * root.stateIntensity

                    to: 0.08

                    duration:
                        1800 * root.animationSpeed

                    easing.type: Easing.InOutSine
                }
            }
        }
    }

    // ==========================================================
    // SCAN LINE
    // ==========================================================

    Rectangle {

        id: scanLine

        width: root.width

        height: root.state === "error" ? 2 : 1

        y: -height

        color: root.stateColor

        opacity:
            root.state === "idle"
            ? 0.08
            : 0.22 * root.stateIntensity

        Behavior on color {

            ColorAnimation {

                duration: Theme.medium
            }
        }

        SequentialAnimation on y {

            running: root.animated

            loops: Animation.Infinite

            NumberAnimation {

                from: -2

                to: root.height + 2

                duration:
                    7000 * root.animationSpeed

                easing.type: Easing.Linear
            }

            PauseAnimation {

                duration: 700
            }
        }
    }

    // ==========================================================
    // ERROR FLASH
    // ==========================================================

    Rectangle {

        anchors.fill: parent

        color: Theme.danger

        opacity: 0

        visible: root.state === "error"

        SequentialAnimation on opacity {

            running: root.animated && root.state === "error"

            loops: Animation.Infinite

            NumberAnimation {

                from: 0

                to: 0.08

                duration: 180
            }

            NumberAnimation {

                from: 0.08

                to: 0

                duration: 280
            }

            PauseAnimation {

                duration: 700
            }
        }
    }

    // ==========================================================
    // EDGE FRAME
    // ==========================================================

    Rectangle {

        anchors.fill: parent

        color: "transparent"

        border.width: 2

        border.color: root.stateColor

        opacity:
            root.state === "error"
            ? 0.22
            : 0.07

        Behavior on border.color {

            ColorAnimation {

                duration: Theme.medium
            }
        }

        Behavior on opacity {

            NumberAnimation {

                duration: Theme.medium
            }
        }
    }
}

