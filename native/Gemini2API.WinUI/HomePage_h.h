/* Header file automatically generated from HomePage.idl */
/*
 * File built with Microsoft(R) MIDLRT Compiler Engine Version 10.00.0231 
 */

#pragma warning( disable: 4049 )  /* more than 64k source lines */

/* verify that the <rpcndr.h> version is high enough to compile this file*/
#ifndef __REQUIRED_RPCNDR_H_VERSION__
#define __REQUIRED_RPCNDR_H_VERSION__ 500
#endif

/* verify that the <rpcsal.h> version is high enough to compile this file*/
#ifndef __REQUIRED_RPCSAL_H_VERSION__
#define __REQUIRED_RPCSAL_H_VERSION__ 100
#endif

#include <rpc.h>
#include <rpcndr.h>

#ifndef __RPCNDR_H_VERSION__
#error this stub requires an updated version of <rpcndr.h>
#endif /* __RPCNDR_H_VERSION__ */

#ifndef COM_NO_WINDOWS_H
#include <windows.h>
#include <ole2.h>
#endif /*COM_NO_WINDOWS_H*/
#ifndef __HomePage_h_h__
#define __HomePage_h_h__
#ifndef __HomePage_h_p_h__
#define __HomePage_h_p_h__


#pragma once

// Ensure that the setting of the /ns_prefix command line switch is consistent for all headers.
// If you get an error from the compiler indicating "warning C4005: 'CHECK_NS_PREFIX_STATE': macro redefinition", this
// indicates that you have included two different headers with different settings for the /ns_prefix MIDL command line switch
#if !defined(DISABLE_NS_PREFIX_CHECKS)
#define CHECK_NS_PREFIX_STATE "never"
#endif // !defined(DISABLE_NS_PREFIX_CHECKS)


#pragma push_macro("MIDL_CONST_ID")
#undef MIDL_CONST_ID
#define MIDL_CONST_ID const __declspec(selectany)


// Header files for imported files
#include "winrtbase.h"
#include "D:\workspaces\2api\gemini2api\native\Gemini2API.WinUI\packages\Microsoft.WindowsAppSDK.InteractiveExperiences.2.0.13\metadata\10.0.17763.0\Microsoft.Foundation.h"
#include "D:\workspaces\2api\gemini2api\native\Gemini2API.WinUI\packages\Microsoft.WindowsAppSDK.InteractiveExperiences.2.0.13\metadata\10.0.17763.0\Microsoft.Graphics.h"
#include "D:\workspaces\2api\gemini2api\native\Gemini2API.WinUI\packages\Microsoft.WindowsAppSDK.WinUI.2.1.0\metadata\Microsoft.UI.Text.h"
#include "D:\workspaces\2api\gemini2api\native\Gemini2API.WinUI\packages\Microsoft.WindowsAppSDK.InteractiveExperiences.2.0.13\metadata\10.0.17763.0\Microsoft.UI.h"
#include "D:\workspaces\2api\gemini2api\native\Gemini2API.WinUI\packages\Microsoft.WindowsAppSDK.WinUI.2.1.0\metadata\Microsoft.UI.Xaml.h"
#include "D:\workspaces\2api\gemini2api\native\Gemini2API.WinUI\packages\Microsoft.Web.WebView2.1.0.3967.48\lib\Microsoft.Web.WebView2.Core.h"
#include "D:\workspaces\2api\gemini2api\native\Gemini2API.WinUI\packages\Microsoft.WindowsAppSDK.Foundation.2.0.21\metadata\Microsoft.Windows.ApplicationModel.Resources.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.AI.Actions.ActionsContract\8.0.0.0\Windows.AI.Actions.ActionsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.AI.Agents.AgentsContract\2.0.0.0\Windows.AI.Agents.AgentsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.AI.MachineLearning.MachineLearningContract\5.0.0.0\Windows.AI.MachineLearning.MachineLearningContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.AI.MachineLearning.Preview.MachineLearningPreviewContract\2.0.0.0\Windows.AI.MachineLearning.Preview.MachineLearningPreviewContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Activation.ActivatedEventsContract\1.0.0.0\Windows.ApplicationModel.Activation.ActivatedEventsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Activation.ActivationCameraSettingsContract\1.0.0.0\Windows.ApplicationModel.Activation.ActivationCameraSettingsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Activation.ContactActivatedEventsContract\1.0.0.0\Windows.ApplicationModel.Activation.ContactActivatedEventsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Activation.WebUISearchActivatedEventsContract\1.0.0.0\Windows.ApplicationModel.Activation.WebUISearchActivatedEventsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Background.BackgroundAlarmApplicationContract\1.0.0.0\Windows.ApplicationModel.Background.BackgroundAlarmApplicationContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Calls.Background.CallsBackgroundContract\4.0.0.0\Windows.ApplicationModel.Calls.Background.CallsBackgroundContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Calls.CallsPhoneContract\7.0.0.0\Windows.ApplicationModel.Calls.CallsPhoneContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Calls.CallsVoipContract\5.0.0.0\Windows.ApplicationModel.Calls.CallsVoipContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Calls.LockScreenCallContract\1.0.0.0\Windows.ApplicationModel.Calls.LockScreenCallContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.CommunicationBlocking.CommunicationBlockingContract\2.0.0.0\Windows.ApplicationModel.CommunicationBlocking.CommunicationBlockingContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.FullTrustAppContract\2.0.0.0\Windows.ApplicationModel.FullTrustAppContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Preview.InkWorkspace.PreviewInkWorkspaceContract\1.0.0.0\Windows.ApplicationModel.Preview.InkWorkspace.PreviewInkWorkspaceContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Preview.Notes.PreviewNotesContract\2.0.0.0\Windows.ApplicationModel.Preview.Notes.PreviewNotesContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Preview.StartupAppsPreviewContract\1.0.0.0\Windows.ApplicationModel.Preview.StartupAppsPreviewContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Resources.Management.ResourceIndexerContract\2.0.0.0\Windows.ApplicationModel.Resources.Management.ResourceIndexerContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Search.Core.SearchCoreContract\1.0.0.0\Windows.ApplicationModel.Search.Core.SearchCoreContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Search.SearchContract\1.0.0.0\Windows.ApplicationModel.Search.SearchContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.SocialInfo.SocialInfoContract\2.0.0.0\Windows.ApplicationModel.SocialInfo.SocialInfoContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.StartupTaskContract\3.0.0.0\Windows.ApplicationModel.StartupTaskContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.ApplicationModel.Wallet.WalletContract\2.0.0.0\Windows.ApplicationModel.Wallet.WalletContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.Custom.CustomDeviceContract\1.0.0.0\Windows.Devices.Custom.CustomDeviceContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.DevicesLowLevelContract\3.0.0.0\Windows.Devices.DevicesLowLevelContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.Portable.PortableDeviceContract\1.0.0.0\Windows.Devices.Portable.PortableDeviceContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.Power.PowerGridApiContract\1.0.0.0\Windows.Devices.Power.PowerGridApiContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.Printers.Extensions.ExtensionsContract\2.0.0.0\Windows.Devices.Printers.Extensions.ExtensionsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.Printers.PrintersContract\1.0.0.0\Windows.Devices.Printers.PrintersContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.Scanners.ScannerDeviceContract\1.0.0.0\Windows.Devices.Scanners.ScannerDeviceContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.SmartCards.SmartCardBackgroundTriggerContract\3.0.0.0\Windows.Devices.SmartCards.SmartCardBackgroundTriggerContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.SmartCards.SmartCardEmulatorContract\6.0.0.0\Windows.Devices.SmartCards.SmartCardEmulatorContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Devices.Sms.LegacySmsApiContract\1.0.0.0\Windows.Devices.Sms.LegacySmsApiContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Foundation.FoundationContract\4.0.0.0\Windows.Foundation.FoundationContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Foundation.UniversalApiContract\19.0.0.0\Windows.Foundation.UniversalApiContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Gaming.Input.GamingInputPreviewContract\2.0.0.0\Windows.Gaming.Input.GamingInputPreviewContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Gaming.Preview.GamesEnumerationContract\2.0.0.0\Windows.Gaming.Preview.GamesEnumerationContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Gaming.UI.GameChatOverlayContract\1.0.0.0\Windows.Gaming.UI.GameChatOverlayContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Gaming.UI.GamingUIProviderContract\1.0.0.0\Windows.Gaming.UI.GamingUIProviderContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Gaming.XboxLive.StorageApiContract\1.0.0.0\Windows.Gaming.XboxLive.StorageApiContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Globalization.GlobalizationJapanesePhoneticAnalyzerContract\1.0.0.0\Windows.Globalization.GlobalizationJapanesePhoneticAnalyzerContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Graphics.Printing3D.Printing3DContract\4.0.0.0\Windows.Graphics.Printing3D.Printing3DContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Management.Deployment.Preview.DeploymentPreviewContract\1.0.0.0\Windows.Management.Deployment.Preview.DeploymentPreviewContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Management.Deployment.SharedPackageContainerContract\1.0.0.0\Windows.Management.Deployment.SharedPackageContainerContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Management.Update.WindowsUpdateContract\2.1.0.0\Windows.Management.Update.WindowsUpdateContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Management.Workplace.WorkplaceSettingsContract\1.0.0.0\Windows.Management.Workplace.WorkplaceSettingsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.AppBroadcasting.AppBroadcastingContract\1.0.0.0\Windows.Media.AppBroadcasting.AppBroadcastingContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.AppRecording.AppRecordingContract\1.0.0.0\Windows.Media.AppRecording.AppRecordingContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Capture.AppBroadcastContract\2.0.0.0\Windows.Media.Capture.AppBroadcastContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Capture.AppCaptureContract\4.0.0.0\Windows.Media.Capture.AppCaptureContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Capture.AppCaptureMetadataContract\1.0.0.0\Windows.Media.Capture.AppCaptureMetadataContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Capture.CameraCaptureUIContract\1.0.0.0\Windows.Media.Capture.CameraCaptureUIContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Capture.GameBarContract\1.0.0.0\Windows.Media.Capture.GameBarContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Devices.CallControlContract\1.0.0.0\Windows.Media.Devices.CallControlContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.MediaControlContract\1.0.0.0\Windows.Media.MediaControlContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Playlists.PlaylistsContract\1.0.0.0\Windows.Media.Playlists.PlaylistsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Media.Protection.ProtectionRenewalContract\1.0.0.0\Windows.Media.Protection.ProtectionRenewalContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Networking.Connectivity.WwanContract\3.0.0.0\Windows.Networking.Connectivity.WwanContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Networking.NetworkOperators.LegacyNetworkOperatorsContract\1.0.0.0\Windows.Networking.NetworkOperators.LegacyNetworkOperatorsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Networking.Sockets.ControlChannelTriggerContract\3.0.0.0\Windows.Networking.Sockets.ControlChannelTriggerContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Networking.XboxLive.XboxLiveSecureSocketsContract\1.0.0.0\Windows.Networking.XboxLive.XboxLiveSecureSocketsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Perception.Automation.Core.PerceptionAutomationCoreContract\1.0.0.0\Windows.Perception.Automation.Core.PerceptionAutomationCoreContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Security.EnterpriseData.EnterpriseDataContract\5.0.0.0\Windows.Security.EnterpriseData.EnterpriseDataContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Security.ExchangeActiveSyncProvisioning.EasContract\1.0.0.0\Windows.Security.ExchangeActiveSyncProvisioning.EasContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Security.Isolation.Isolatedwindowsenvironmentcontract\5.0.0.0\Windows.Security.Isolation.Isolatedwindowsenvironmentcontract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Services.Maps.GuidanceContract\3.0.0.0\Windows.Services.Maps.GuidanceContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Services.Maps.LocalSearchContract\4.0.0.0\Windows.Services.Maps.LocalSearchContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Services.Store.StoreContract\4.0.0.0\Windows.Services.Store.StoreContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Services.TargetedContent.TargetedContentContract\1.0.0.0\Windows.Services.TargetedContent.TargetedContentContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Storage.Provider.CloudFilesContract\7.0.0.0\Windows.Storage.Provider.CloudFilesContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.Power.Thermal.PowerThermalApiContract\1.0.0.0\Windows.System.Power.Thermal.PowerThermalApiContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\windows.system.profile.platformautomaticappsignincontract\1.0.0.0\windows.system.profile.platformautomaticappsignincontract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.Profile.ProfileHardwareTokenContract\1.0.0.0\Windows.System.Profile.ProfileHardwareTokenContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.Profile.ProfileRetailInfoContract\1.0.0.0\Windows.System.Profile.ProfileRetailInfoContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.Profile.ProfileSharedModeContract\2.0.0.0\Windows.System.Profile.ProfileSharedModeContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.Profile.SystemManufacturers.SystemManufacturersContract\3.0.0.0\Windows.System.Profile.SystemManufacturers.SystemManufacturersContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.SystemManagementContract\7.0.0.0\Windows.System.SystemManagementContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.UserProfile.UserProfileContract\2.0.0.0\Windows.System.UserProfile.UserProfileContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.System.UserProfile.UserProfileLockScreenContract\1.0.0.0\Windows.System.UserProfile.UserProfileLockScreenContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.ApplicationSettings.ApplicationsSettingsContract\1.0.0.0\Windows.UI.ApplicationSettings.ApplicationsSettingsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Core.AnimationMetrics.AnimationMetricsContract\1.0.0.0\Windows.UI.Core.AnimationMetrics.AnimationMetricsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Core.CoreWindowDialogsContract\1.0.0.0\Windows.UI.Core.CoreWindowDialogsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Input.Preview.Text.PreviewTextContract\1.0.0.0\Windows.UI.Input.Preview.Text.PreviewTextContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Shell.CompanionWindows.CompanionWindowsContract\1.0.0.0\Windows.UI.Shell.CompanionWindows.CompanionWindowsContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Shell.SecurityAppManagerContract\1.0.0.0\Windows.UI.Shell.SecurityAppManagerContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Shell.Tasks.AppTaskContract\2.0.0.0\Windows.UI.Shell.Tasks.AppTaskContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Shell.WindowTabManagerContract\1.0.0.0\Windows.UI.Shell.WindowTabManagerContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.UIAutomation.UIAutomationContract\2.0.0.0\Windows.UI.UIAutomation.UIAutomationContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.ViewManagement.ViewManagementViewScalingContract\1.0.0.0\Windows.UI.ViewManagement.ViewManagementViewScalingContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Xaml.Core.Direct.XamlDirectContract\5.0.0.0\Windows.UI.Xaml.Core.Direct.XamlDirectContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.UI.Xaml.Hosting.HostingContract\5.0.0.0\Windows.UI.Xaml.Hosting.HostingContract.h"
#include "C:\Program Files (x86)\Windows Kits\10\References\10.0.26100.0\Windows.Web.Http.Diagnostics.HttpDiagnosticsContract\2.0.0.0\Windows.Web.Http.Diagnostics.HttpDiagnosticsContract.h"

#if defined(__cplusplus) && !defined(CINTERFACE)
/* Forward Declarations */
#ifndef ____x_Gemini2API_CViews_CIHomePage_FWD_DEFINED__
#define ____x_Gemini2API_CViews_CIHomePage_FWD_DEFINED__

namespace Gemini2API {
    namespace Views {
        interface IHomePage;
    } /* Views */
} /* Gemini2API */
#define __x_Gemini2API_CViews_CIHomePage Gemini2API::Views::IHomePage

#endif // ____x_Gemini2API_CViews_CIHomePage_FWD_DEFINED__



namespace Gemini2API {
    namespace Views {
        class HomePage;
    } /* Views */
} /* Gemini2API */



/*
 *
 * Interface Gemini2API.Views.IHomePage
 *
 * Interface is a part of the implementation of type Gemini2API.Views.HomePage
 *
 *
 * The IID for this interface was automatically generated by MIDLRT.
 *
 * Interface IID generation seed: Gemini2API.Views.IHomePage:
 *
 *
 */
#if !defined(____x_Gemini2API_CViews_CIHomePage_INTERFACE_DEFINED__)
#define ____x_Gemini2API_CViews_CIHomePage_INTERFACE_DEFINED__
extern const __declspec(selectany) _Null_terminated_ WCHAR InterfaceName_Gemini2API_Views_IHomePage[] = L"Gemini2API.Views.IHomePage";

namespace Gemini2API {
    namespace Views {
        /* [uuid("0b4a605d-11ac-5379-937a-9c6165f42f80"), version, object, exclusiveto] */
        MIDL_INTERFACE("0b4a605d-11ac-5379-937a-9c6165f42f80")
        IHomePage : public IInspectable
        {
        public:
            
        };

        MIDL_CONST_ID IID & IID_IHomePage=__uuidof(IHomePage);
        
    } /* Views */
} /* Gemini2API */

EXTERN_C const IID IID___x_Gemini2API_CViews_CIHomePage;
#endif /* !defined(____x_Gemini2API_CViews_CIHomePage_INTERFACE_DEFINED__) */


/*
 *
 * Class Gemini2API.Views.HomePage
 *
 * RuntimeClass can be activated.
 *
 * Class implements the following interfaces:
 *    Gemini2API.Views.IHomePage ** Default Interface **
 *
 * Class Threading Model:  Both Single and Multi Threaded Apartment
 *
 * Class Marshaling Behavior:  Agile - Class is agile
 *
 */

#ifndef RUNTIMECLASS_Gemini2API_Views_HomePage_DEFINED
#define RUNTIMECLASS_Gemini2API_Views_HomePage_DEFINED
extern const __declspec(selectany) _Null_terminated_ WCHAR RuntimeClass_Gemini2API_Views_HomePage[] = L"Gemini2API.Views.HomePage";
#endif


#else // !defined(__cplusplus)
/* Forward Declarations */
#ifndef ____x_Gemini2API_CViews_CIHomePage_FWD_DEFINED__
#define ____x_Gemini2API_CViews_CIHomePage_FWD_DEFINED__
typedef interface __x_Gemini2API_CViews_CIHomePage __x_Gemini2API_CViews_CIHomePage;

#endif // ____x_Gemini2API_CViews_CIHomePage_FWD_DEFINED__



/*
 *
 * Interface Gemini2API.Views.IHomePage
 *
 * Interface is a part of the implementation of type Gemini2API.Views.HomePage
 *
 *
 * The IID for this interface was automatically generated by MIDLRT.
 *
 * Interface IID generation seed: Gemini2API.Views.IHomePage:
 *
 *
 */
#if !defined(____x_Gemini2API_CViews_CIHomePage_INTERFACE_DEFINED__)
#define ____x_Gemini2API_CViews_CIHomePage_INTERFACE_DEFINED__
extern const __declspec(selectany) _Null_terminated_ WCHAR InterfaceName_Gemini2API_Views_IHomePage[] = L"Gemini2API.Views.IHomePage";
/* [uuid("0b4a605d-11ac-5379-937a-9c6165f42f80"), version, object, exclusiveto] */
typedef struct __x_Gemini2API_CViews_CIHomePageVtbl
{
    BEGIN_INTERFACE
    HRESULT ( STDMETHODCALLTYPE *QueryInterface)(
    __RPC__in __x_Gemini2API_CViews_CIHomePage * This,
    /* [in] */ __RPC__in REFIID riid,
    /* [annotation][iid_is][out] */
    _COM_Outptr_  void **ppvObject
    );

ULONG ( STDMETHODCALLTYPE *AddRef )(
    __RPC__in __x_Gemini2API_CViews_CIHomePage * This
    );

ULONG ( STDMETHODCALLTYPE *Release )(
    __RPC__in __x_Gemini2API_CViews_CIHomePage * This
    );

HRESULT ( STDMETHODCALLTYPE *GetIids )(
    __RPC__in __x_Gemini2API_CViews_CIHomePage * This,
    /* [out] */ __RPC__out ULONG *iidCount,
    /* [size_is][size_is][out] */ __RPC__deref_out_ecount_full_opt(*iidCount) IID **iids
    );

HRESULT ( STDMETHODCALLTYPE *GetRuntimeClassName )(
    __RPC__in __x_Gemini2API_CViews_CIHomePage * This,
    /* [out] */ __RPC__deref_out_opt HSTRING *className
    );

HRESULT ( STDMETHODCALLTYPE *GetTrustLevel )(
    __RPC__in __x_Gemini2API_CViews_CIHomePage * This,
    /* [OUT ] */ __RPC__out TrustLevel *trustLevel
    );
END_INTERFACE
    
} __x_Gemini2API_CViews_CIHomePageVtbl;

interface __x_Gemini2API_CViews_CIHomePage
{
    CONST_VTBL struct __x_Gemini2API_CViews_CIHomePageVtbl *lpVtbl;
};

#ifdef COBJMACROS
#define __x_Gemini2API_CViews_CIHomePage_QueryInterface(This,riid,ppvObject) \
( (This)->lpVtbl->QueryInterface(This,riid,ppvObject) )

#define __x_Gemini2API_CViews_CIHomePage_AddRef(This) \
        ( (This)->lpVtbl->AddRef(This) )

#define __x_Gemini2API_CViews_CIHomePage_Release(This) \
        ( (This)->lpVtbl->Release(This) )

#define __x_Gemini2API_CViews_CIHomePage_GetIids(This,iidCount,iids) \
        ( (This)->lpVtbl->GetIids(This,iidCount,iids) )

#define __x_Gemini2API_CViews_CIHomePage_GetRuntimeClassName(This,className) \
        ( (This)->lpVtbl->GetRuntimeClassName(This,className) )

#define __x_Gemini2API_CViews_CIHomePage_GetTrustLevel(This,trustLevel) \
        ( (This)->lpVtbl->GetTrustLevel(This,trustLevel) )


#endif /* COBJMACROS */


EXTERN_C const IID IID___x_Gemini2API_CViews_CIHomePage;
#endif /* !defined(____x_Gemini2API_CViews_CIHomePage_INTERFACE_DEFINED__) */


/*
 *
 * Class Gemini2API.Views.HomePage
 *
 * RuntimeClass can be activated.
 *
 * Class implements the following interfaces:
 *    Gemini2API.Views.IHomePage ** Default Interface **
 *
 * Class Threading Model:  Both Single and Multi Threaded Apartment
 *
 * Class Marshaling Behavior:  Agile - Class is agile
 *
 */

#ifndef RUNTIMECLASS_Gemini2API_Views_HomePage_DEFINED
#define RUNTIMECLASS_Gemini2API_Views_HomePage_DEFINED
extern const __declspec(selectany) _Null_terminated_ WCHAR RuntimeClass_Gemini2API_Views_HomePage[] = L"Gemini2API.Views.HomePage";
#endif


#endif // defined(__cplusplus)
#pragma pop_macro("MIDL_CONST_ID")
#endif // __HomePage_h_p_h__

#endif // __HomePage_h_h__
