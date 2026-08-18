import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import Kraken

Rectangle {

    id: root

    color: Theme.surface

    border.color: Theme.border
    border.width: 1

    implicitHeight: Theme.topBarHeight

    // ----------------------------------------------------------
    // Status
    //
    // Exposed as bindable properties so a backend (context
    // property, singleton, etc.) can bind to them later without
    // any changes needed here.
    //
    // e.g. root.statusText: SystemMonitor.online ? "ONLINE" : "OFFLINE"
    //      root.statusState: SystemMonitor.online ? "success" : "danger"
    // ----------------------------------------------------------

    property string statusText: "ONLINE"
    property string statusState: "success"

    readonly property color statusColor: {

        switch (statusState) {

        case "success":
            return Theme.accentGreen

        case "warning":
            return Theme.warning

        case "danger":
            return Theme.danger

        default:
            return Theme.accent
        }
    }

    RowLayout {

        anchors.fill: parent

        anchors.leftMargin: Theme.spacingXL
        anchors.rightMargin: Theme.spacingXL

        spacing: Theme.spacingL

        Text {

            text: Theme.appName

            color: Theme.textPrimary

            font.pixelSize: Theme.fontTitle
            font.bold: true
        }

        Item {
            Layout.fillWidth: true
        }

        Rectangle {

            width: 12
            height: 12

            radius: 6

            color: root.statusColor

            SequentialAnimation on opacity {

                loops: Animation.Infinite

                NumberAnimation {
                    from: 1.0
                    to: 0.35
                    duration: 900
                }

                NumberAnimation {
                    from: 0.35
                    to: 1.0
                    duration: 900
                }
            }
        }

        Text {

            text: root.statusText

            color: root.statusColor

            font.pixelSize: Theme.fontBody

            font.bold: true
        }
    }
}
