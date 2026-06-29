"""Application progress API routes."""

from flask import Blueprint, current_app, jsonify, request, g
from models.application_progress import ApplicationProgress
from models.user import get_role_permissions, get_user_by_id, staff_may_access_target_user_workspace
from services.notification_service import (
    EVENT_CASE_STAGE_CHANGED,
    notify,
    stage_title,
)

bp = Blueprint('application_progress', __name__)


def _can_manage_application_progress(current_user, target_user_id: int) -> bool:
    permissions = set(get_role_permissions(current_user["role_key"] or ""))
    can_edit_cases = bool(
        {
            "full_access",
            "view_all_users",
            "view_lower_users",
            "view_assignable_users",
            "view_assigned_clients",
            "communicate_with_clients",
            "respond_to_applications",
        }
        & permissions
    )
    if not can_edit_cases:
        return False
    if int(current_user["id"]) == int(target_user_id):
        return True
    return staff_may_access_target_user_workspace(
        g.db, int(current_user["id"]), int(target_user_id)
    )


@bp.route('/api/application/progress', methods=['GET'])
def get_progress():
    """Get application progress for current user."""
    try:
        current_user_id = g.current_user_id
        
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        # Get user's application type from profile
        user = get_user_by_id(g.db, current_user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        application_type = user['application_type'] or 'vnj_investment'
        current_stage = user['current_stage'] or 'consultation'
        
        # Generate progress data
        progress_data = ApplicationProgress.create_progress(
            user_id=current_user_id,
            application_type=application_type,
            current_stage_id=current_stage
        )
        
        return jsonify(progress_data), 200
        
    except Exception:
        current_app.logger.exception("failed to get application progress")
        return jsonify({'success': False, 'error': 'internal server error'}), 500


@bp.route('/api/application/progress/<int:user_id>', methods=['GET'])
def get_user_progress(user_id):
    """Get application progress for specific user (admin only)."""
    try:
        current_user_id = g.current_user_id
        
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        current_user = get_user_by_id(g.db, current_user_id)
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        if user_id != current_user_id and not _can_manage_application_progress(current_user, user_id):
            return jsonify({'error': 'Access denied'}), 403

        # Get target user
        user = get_user_by_id(g.db, user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        application_type = user['application_type'] or 'vnj_investment'
        current_stage = user['current_stage'] or 'consultation'
        
        progress_data = ApplicationProgress.create_progress(
            user_id=user_id,
            application_type=application_type,
            current_stage_id=current_stage
        )
        
        return jsonify(progress_data), 200
        
    except Exception:
        current_app.logger.exception("failed to get user application progress")
        return jsonify({'success': False, 'error': 'internal server error'}), 500


@bp.route('/api/application/progress/<int:user_id>', methods=['PUT'])
def update_user_progress(user_id):
    """Update application progress for specific user (admin/manager only)."""
    try:
        current_user_id = g.current_user_id
        
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        current_user = get_user_by_id(g.db, current_user_id)
        if not current_user:
            return jsonify({'error': 'User not found'}), 404
        
        if not _can_manage_application_progress(current_user, user_id):
            return jsonify({'error': 'Access denied'}), 403
        
        data = request.get_json()
        new_stage_id = data.get('current_stage_id')
        
        if not new_stage_id:
            return jsonify({'error': 'current_stage_id is required'}), 400
        
        # Get current user data
        user = get_user_by_id(g.db, user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        application_type = user['application_type'] or 'vnj_investment'
        old_stage_id = user['current_stage'] or 'consultation'
        
        # Validate that the stage exists for this application type
        stages = ApplicationProgress.get_stages_for_type(application_type)
        valid_stage_ids = [stage.stage_id for stage in stages]
        
        if new_stage_id not in valid_stage_ids:
            return jsonify({
                'error': f'Invalid stage_id for application type {application_type}',
                'valid_stages': valid_stage_ids
            }), 400
        
        # Update user's current stage in database
        cursor = g.db.cursor()
        cursor.execute(
            'UPDATE users SET current_stage = ? WHERE id = ?',
            (new_stage_id, user_id)
        )
        g.db.commit()

        if old_stage_id != new_stage_id:
            locale = "en" if str(user["locale"] or "ru").strip().lower() == "en" else "ru"
            notify(
                g.db,
                user_id,
                EVENT_CASE_STAGE_CHANGED,
                {
                    "stage_id": new_stage_id,
                    "stage_title": stage_title(application_type, new_stage_id, locale),
                },
            )
        
        # Generate updated progress data
        progress_data = ApplicationProgress.create_progress(
            user_id=user_id,
            application_type=application_type,
            current_stage_id=new_stage_id
        )
        
        return jsonify({
            'message': 'Progress updated successfully',
            'progress': progress_data
        }), 200
        
    except Exception:
        current_app.logger.exception("failed to update user application progress")
        return jsonify({'success': False, 'error': 'internal server error'}), 500


@bp.route('/api/application/types', methods=['GET'])
def get_application_types():
    """Get available application types and their stages."""
    try:
        current_user_id = g.current_user_id
        
        if not current_user_id:
            return jsonify({'error': 'Unauthorized'}), 401
        
        types_info = {}
        
        for app_type, stages in ApplicationProgress.STAGES_BY_TYPE.items():
            types_info[app_type] = {
                'name': app_type,
                'stages': stages
            }
        
        return jsonify(types_info), 200
        
    except Exception:
        current_app.logger.exception("failed to get application types")
        return jsonify({'success': False, 'error': 'internal server error'}), 500
