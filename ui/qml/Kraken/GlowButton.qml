
import QtQuick
import QtQuick.Controls

import Kraken

Button {

    id: control

    // ----------------------------------------------------------
    // Public API
    // ----------------------------------------------------------

    property color glowColor: Theme.accent

    property color textColor: Theme.background

    property real glowStrength: 0.18

    property bool showGlow: true

    // ----------------------------------------------------------
    // Dimensions
    // ----------------------------------------------------------

    implicitWidth: 140
    implicitHeight: Theme.buttonHeight

    leftPadding: Theme.spacingL
    rightPadding: Theme.spacingL

    // ----------------------------------------------------------
    // Hover / interaction state
    // ----------------------------------------------------------

    hoverEnabled: true

    scale: {

        if (control.down)
            return 0.96

        if (control.hovered)
            return 1.02

        return 1.0
    }

    Behavior on scale {

        NumberAnimation {

            duration: Theme.fast

            easing.type: Easing.OutCubic
        }
    }

    // ----------------------------------------------------------
    // Glow
    // ----------------------------------------------------------

    Rectangle {

        id: glow

        anchors.fill: background

        anchors.margins: -6

        radius: Theme.radiusMedium + 6

        color: "transparent"

        border.width: 2

        border.color: control.glowColor

        opacity: {

            if (!control.showGlow)
                return 0

            if (control.down)
                return 0.35

            if (control.hovered)
                return control.glowStrength * 3

            return control.glowStrength
        }

        z: -1

        Behavior on opacity {

            NumberAnimation {

                duration: Theme.medium

            }
        }
    }

    // ----------------------------------------------------------
    // Button background
    // ----------------------------------------------------------

    background: Rectangle {

        id: buttonBackground

        radius: Theme.radiusMedium

        color: {

            if (control.down)
                return Qt.darker(control.glowColor, 1.25)

            if (control.hovered)
                return Qt.lighter(control.glowColor, 1.08)

            return control.glowColor
        }

        border.width: 1

        border.color: Qt.lighter(
            control.glowColor,
            1.25
        )

        Behavior on color {

            ColorAnimation {

                duration: Theme.fast

            }
        }

        Behavior on border.color {

            ColorAnimation {

                duration: Theme.fast

            }
        }
    }

    // ----------------------------------------------------------
    // Button content
    // ----------------------------------------------------------

    contentItem: Text {

        text: control.text

        color: control.textColor

        font.pixelSize: Theme.fontBody

        font.bold: true

        horizontalAlignment: Text.AlignHCenter

        verticalAlignment: Text.AlignVCenter

        elide: Text.ElideRight
    }
}

