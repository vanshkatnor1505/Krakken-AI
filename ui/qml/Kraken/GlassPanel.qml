
import QtQuick

import Kraken

Rectangle {

    id: panel

    // ----------------------------------------------------------
    // Public properties
    // ----------------------------------------------------------

    property bool interactive: true
    property bool hoverEffect: true

    property color panelColor: Theme.surface
    property color hoverColor: Theme.surfaceLight
    property color borderColor: Theme.border

    // ----------------------------------------------------------
    // Base appearance
    // ----------------------------------------------------------

    color: panelColor

    radius: Theme.radiusLarge

    border.width: 1
    border.color: borderColor

    opacity: Theme.glassOpacity

    // ----------------------------------------------------------
    // Hover state
    // ----------------------------------------------------------

    property bool hovered: false

    scale: hovered && hoverEffect ? 1.008 : 1.0

    Behavior on scale {

        NumberAnimation {

            duration: Theme.fast

            easing.type: Easing.OutCubic
        }
    }

    Behavior on color {

        ColorAnimation {

            duration: Theme.medium
        }
    }

    Behavior on opacity {

        NumberAnimation {

            duration: Theme.medium
        }
    }

    // ----------------------------------------------------------
    // Content container
    //
    // Anything placed inside GlassPanel automatically becomes
    // a child of this Rectangle.
    // ----------------------------------------------------------

    default property alias content: contentContainer.data

    Item {

        id: contentContainer

        anchors.fill: parent

        anchors.margins: 1
    }

    // ----------------------------------------------------------
    // Interaction layer
    // ----------------------------------------------------------

    MouseArea {

        id: mouseArea

        anchors.fill: parent

        enabled: panel.interactive

        hoverEnabled: true

        acceptedButtons: Qt.NoButton

        cursorShape: Qt.ArrowCursor

        onEntered: {

            panel.hovered = true

            panel.color = panel.hoverColor
        }

        onExited: {

            panel.hovered = false

            panel.color = panel.panelColor
        }
    }
}
