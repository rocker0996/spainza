"""Application progress model for tracking client application stages."""

from datetime import datetime
from typing import Dict, List, Optional


class ApplicationStage:
    """Represents a single stage in the application process."""
    
    def __init__(
        self,
        stage_id: str,
        title_ru: str,
        title_en: str,
        description_ru: str,
        description_en: str,
        order: int,
        is_completed: bool = False,
        is_active: bool = False,
        completed_date: Optional[str] = None
    ):
        self.stage_id = stage_id
        self.title_ru = title_ru
        self.title_en = title_en
        self.description_ru = description_ru
        self.description_en = description_en
        self.order = order
        self.is_completed = is_completed
        self.is_active = is_active
        self.completed_date = completed_date
    
    def to_dict(self) -> Dict:
        """Convert stage to dictionary."""
        return {
            'stage_id': self.stage_id,
            'title_ru': self.title_ru,
            'title_en': self.title_en,
            'description_ru': self.description_ru,
            'description_en': self.description_en,
            'order': self.order,
            'is_completed': self.is_completed,
            'is_active': self.is_active,
            'completed_date': self.completed_date
        }


class ApplicationProgress:
    """Manages application progress tracking."""
    
    # Predefined stages for different application types
    STAGES_BY_TYPE = {
        'vnj_investment': [
            {
                'stage_id': 'consultation',
                'title_ru': 'Первичная консультация и стратегия',
                'title_en': 'Initial Consultation & Strategy',
                'description_ru': 'Анализ вашей ситуации и выбор оптимального пути',
                'description_en': 'Analysis of your situation and choosing the optimal path',
                'order': 1
            },
            {
                'stage_id': 'documents',
                'title_ru': 'Сбор документов',
                'title_en': 'Document Gathering',
                'description_ru': 'Подготовка всех необходимых документов',
                'description_en': 'Preparation of all required documents',
                'order': 2
            },
            {
                'stage_id': 'legal_review',
                'title_ru': 'Юридическая проверка и перевод',
                'title_en': 'Legal Review & Translation',
                'description_ru': 'Проверка документов и заверенные переводы',
                'description_en': 'Document verification and sworn translations',
                'order': 3
            },
            {
                'stage_id': 'submission',
                'title_ru': 'Подача в министерство',
                'title_en': 'Submission to Ministry',
                'description_ru': 'Официальная подача заявки в государственные органы',
                'description_en': 'Official submission to government authorities',
                'order': 4
            },
            {
                'stage_id': 'processing',
                'title_ru': 'Обработка государственными органами',
                'title_en': 'Government Processing',
                'description_ru': 'Рассмотрение заявки (20-40 рабочих дней)',
                'description_en': 'Application review (20-40 business days)',
                'order': 5
            },
            {
                'stage_id': 'approval',
                'title_ru': 'Одобрение и получение ВНЖ',
                'title_en': 'Approval & Residence Permit',
                'description_ru': 'Получение одобрения и оформление документов',
                'description_en': 'Receiving approval and document processing',
                'order': 6
            }
        ],
        'business_immigration': [
            {
                'stage_id': 'consultation',
                'title_ru': 'Бизнес-консультация',
                'title_en': 'Business Consultation',
                'description_ru': 'Анализ бизнес-плана и требований',
                'description_en': 'Business plan analysis and requirements',
                'order': 1
            },
            {
                'stage_id': 'company_setup',
                'title_ru': 'Регистрация компании',
                'title_en': 'Company Registration',
                'description_ru': 'Создание юридического лица в Испании',
                'description_en': 'Legal entity creation in Spain',
                'order': 2
            },
            {
                'stage_id': 'documents',
                'title_ru': 'Подготовка документов',
                'title_en': 'Document Preparation',
                'description_ru': 'Сбор корпоративных и личных документов',
                'description_en': 'Corporate and personal document collection',
                'order': 3
            },
            {
                'stage_id': 'submission',
                'title_ru': 'Подача заявки',
                'title_en': 'Application Submission',
                'description_ru': 'Подача на бизнес-визу/ВНЖ',
                'description_en': 'Business visa/residence permit application',
                'order': 4
            },
            {
                'stage_id': 'processing',
                'title_ru': 'Рассмотрение',
                'title_en': 'Processing',
                'description_ru': 'Обработка заявки государственными органами',
                'description_en': 'Government processing of application',
                'order': 5
            },
            {
                'stage_id': 'approval',
                'title_ru': 'Одобрение',
                'title_en': 'Approval',
                'description_ru': 'Получение разрешения на ведение бизнеса',
                'description_en': 'Receiving business authorization',
                'order': 6
            }
        ],
        'family_reunification': [
            {
                'stage_id': 'consultation',
                'title_ru': 'Консультация',
                'title_en': 'Consultation',
                'description_ru': 'Оценка возможности воссоединения семьи',
                'description_en': 'Family reunification eligibility assessment',
                'order': 1
            },
            {
                'stage_id': 'documents',
                'title_ru': 'Сбор документов',
                'title_en': 'Document Collection',
                'description_ru': 'Подготовка семейных и личных документов',
                'description_en': 'Family and personal document preparation',
                'order': 2
            },
            {
                'stage_id': 'legalization',
                'title_ru': 'Легализация документов',
                'title_en': 'Document Legalization',
                'description_ru': 'Апостиль и переводы документов',
                'description_en': 'Apostille and document translations',
                'order': 3
            },
            {
                'stage_id': 'submission',
                'title_ru': 'Подача заявки',
                'title_en': 'Application Submission',
                'description_ru': 'Официальная подача на воссоединение',
                'description_en': 'Official reunification application',
                'order': 4
            },
            {
                'stage_id': 'processing',
                'title_ru': 'Рассмотрение',
                'title_en': 'Processing',
                'description_ru': 'Обработка заявки (30-60 дней)',
                'description_en': 'Application processing (30-60 days)',
                'order': 5
            },
            {
                'stage_id': 'approval',
                'title_ru': 'Одобрение',
                'title_en': 'Approval',
                'description_ru': 'Получение разрешения на въезд',
                'description_en': 'Entry authorization received',
                'order': 6
            }
        ],
        'consultation': [
            {
                'stage_id': 'initial',
                'title_ru': 'Первичная консультация',
                'title_en': 'Initial Consultation',
                'description_ru': 'Обсуждение вашей ситуации',
                'description_en': 'Discussion of your situation',
                'order': 1
            },
            {
                'stage_id': 'analysis',
                'title_ru': 'Анализ документов',
                'title_en': 'Document Analysis',
                'description_ru': 'Изучение предоставленных материалов',
                'description_en': 'Review of provided materials',
                'order': 2
            },
            {
                'stage_id': 'recommendations',
                'title_ru': 'Рекомендации',
                'title_en': 'Recommendations',
                'description_ru': 'Подготовка плана действий',
                'description_en': 'Action plan preparation',
                'order': 3
            },
            {
                'stage_id': 'completed',
                'title_ru': 'Завершено',
                'title_en': 'Completed',
                'description_ru': 'Консультация завершена',
                'description_en': 'Consultation completed',
                'order': 4
            }
        ]
    }
    
    @staticmethod
    def get_stages_for_type(application_type: str) -> List[ApplicationStage]:
        """Get stages for a specific application type."""
        stage_templates = ApplicationProgress.STAGES_BY_TYPE.get(
            application_type,
            ApplicationProgress.STAGES_BY_TYPE['vnj_investment']  # Default
        )
        
        return [
            ApplicationStage(
                stage_id=stage['stage_id'],
                title_ru=stage['title_ru'],
                title_en=stage['title_en'],
                description_ru=stage['description_ru'],
                description_en=stage['description_en'],
                order=stage['order']
            )
            for stage in stage_templates
        ]
    
    @staticmethod
    def create_progress(
        user_id: int,
        application_type: str,
        current_stage_id: str = 'consultation'
    ) -> Dict:
        """Create progress data for a user."""
        stages = ApplicationProgress.get_stages_for_type(application_type)
        
        # Mark stages as completed or active based on current stage
        current_stage_order = None
        for stage in stages:
            if stage.stage_id == current_stage_id:
                current_stage_order = stage.order
                stage.is_active = True
                break
        
        if current_stage_order:
            for stage in stages:
                if stage.order < current_stage_order:
                    stage.is_completed = True
                    stage.completed_date = datetime.now().isoformat()
        
        # Calculate progress percentage
        total_stages = len(stages)
        completed_stages = sum(1 for s in stages if s.is_completed)
        progress_percentage = int((completed_stages / total_stages) * 100) if total_stages > 0 else 0
        
        return {
            'user_id': user_id,
            'application_type': application_type,
            'current_stage_id': current_stage_id,
            'progress_percentage': progress_percentage,
            'stages': [stage.to_dict() for stage in stages],
            'updated_at': datetime.now().isoformat()
        }
    
    @staticmethod
    def update_progress(
        progress_data: Dict,
        new_stage_id: str
    ) -> Dict:
        """Update progress to a new stage."""
        stages = [
            ApplicationStage(**stage_dict)
            for stage_dict in progress_data['stages']
        ]
        
        # Reset all stages
        for stage in stages:
            stage.is_active = False
            stage.is_completed = False
            stage.completed_date = None
        
        # Update based on new stage
        current_stage_order = None
        for stage in stages:
            if stage.stage_id == new_stage_id:
                current_stage_order = stage.order
                stage.is_active = True
                break
        
        if current_stage_order:
            for stage in stages:
                if stage.order < current_stage_order:
                    stage.is_completed = True
                    stage.completed_date = datetime.now().isoformat()
        
        # Calculate progress percentage
        total_stages = len(stages)
        completed_stages = sum(1 for s in stages if s.is_completed)
        progress_percentage = int((completed_stages / total_stages) * 100) if total_stages > 0 else 0
        
        progress_data['current_stage_id'] = new_stage_id
        progress_data['progress_percentage'] = progress_percentage
        progress_data['stages'] = [stage.to_dict() for stage in stages]
        progress_data['updated_at'] = datetime.now().isoformat()
        
        return progress_data
